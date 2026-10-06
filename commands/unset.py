from rich.console import Console

from pyos import shellvars

console = Console()
config = {"name": "unset", "description": "Forget a variable (unset NAME)."}


def execute(args=None):
    if not args:
        console.print("[bold red]Usage:[/bold red] unset NAME...")
        return False
    for name in args:
        shellvars.unset(name)
    return True
