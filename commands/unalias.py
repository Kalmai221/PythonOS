from rich.console import Console

from pyos import shellvars

console = Console()
config = {"name": "unalias", "description": "Remove an alias (unalias <name>, or unalias -a for all)."}


def execute(args=None):
    args = list(args or [])
    if not args:
        console.print("[bold red]Usage:[/bold red] unalias <name>...   or   unalias -a")
        return False
    if args == ["-a"]:
        shellvars.clear_aliases()
        return True
    ok = True
    for name in args:
        if not shellvars.remove_alias(name):
            console.print(f"[bold red]unalias: {name}: not found[/bold red]")
            ok = False
    return ok
