from rich.console import Console
from rich.markup import escape

import pyos
import pyos.fs as fs
from pyos import trash
from pyos.log import log

console = Console()
config = {"name": "undo", "description": "Bring back the last thing rm removed (undo [N] for the last N)"}


def execute(args=None):
    args = list(args or [])
    count = int(args[0]) if args and args[0].isdigit() else 1
    user, _role = pyos.userinfo()
    items = sorted(trash.mine(user), key=lambda i: i["time"], reverse=True)
    if not items:
        console.print("[dim]Nothing to undo: the trash is empty.[/dim]")
        return False
    ok = True
    for item in items[:count]:
        try:
            where = trash.restore(item)
            log(f"undo rm {item['from']}", user=user)
            console.print(f"[green]Restored {escape(fs.display(where, tilde=True))}[/green]")
        except Exception as e:
            console.print(f"[bold red]undo: {escape(item['name'])}: {escape(fs.errtext(e))}[/bold red]")
            ok = False
    return ok
