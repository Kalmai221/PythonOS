import shlex

from rich.console import Console

from pyos import shellvars

console = Console()
config = {"name": "alias", "description": "Give a command a short name (alias ll=\"ls -l\"); alias alone lists them; they are kept for you."}


def quote(value):
    return shlex.quote(value) if value else "''"


def execute(args=None):
    args = list(args or [])
    if not args:
        found = shellvars.aliases()
        if not found:
            console.print("[dim]No aliases yet. Make one with: alias ll=\"ls -l\"[/dim]")
        for name, value in found.items():
            console.print(f"alias {name}={quote(value)}", markup=False, highlight=False)
        return True
    ok = True
    for item in args:
        name, sep, value = item.partition("=")
        if not sep:
            known = shellvars.aliases()
            if name in known:
                console.print(f"alias {name}={quote(known[name])}", markup=False, highlight=False)
            else:
                console.print(f"[bold red]alias: {name}: not found[/bold red]")
                ok = False
            continue
        try:
            shellvars.set_alias(name, value)
        except ValueError as e:
            console.print(f"[bold red]alias: {e}[/bold red]")
            ok = False
    return ok
