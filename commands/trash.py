import time

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm
from rich.table import Table

import pyos
import pyos.fs as fs
from pyos import trash
from pyos.log import log

console = Console()
config = {"name": "trash", "description": "The trash: trash [list|restore <item> [path]|delete <item>|empty] (rm puts things here)"}

USAGE = ("[bold red]Usage:[/bold red] trash \\[list \\[--all]] | restore <number|name> \\[path] | delete <number|name> | empty \\[--all]")


def human(size):
    for unit in ("B", "K", "M", "G"):
        if size < 1024 or unit == "G":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024


def show(user, admin, everyone):
    items = sorted(trash.mine(user, admin, everyone), key=lambda i: i["time"], reverse=True)
    if not items:
        console.print("[dim]The trash is empty.[/dim]")
        return True
    table = Table(header_style="bold blue")
    for col in ("#", "Name", "Was in", "Size", "Removed") + (("By",) if everyone and admin else ()):
        table.add_column(col)
    for n, i in enumerate(items, 1):
        row = [str(n), escape(i["name"]) + ("/" if i["dir"] else ""), escape(i["from"].rsplit("/", 1)[0] or "/"), human(i["size"]),
               time.strftime("%Y-%m-%d %H:%M", time.localtime(i["time"]))]
        if everyone and admin:
            row.append(escape(i["user"]))
        table.add_row(*row)
    console.print(table)
    console.print("[dim]trash restore <number>   |   trash delete <number>   |   trash empty[/dim]")
    return True


def execute(args=None):
    args = list(args or [])
    everyone = "--all" in args
    args = [a for a in args if a != "--all"]
    user, role = pyos.userinfo()
    admin = role == "admin"
    sub = args[0] if args else "list"
    if sub == "list":
        return show(user, admin, everyone)
    if sub == "empty":
        count = len(trash.mine(user, admin, everyone))
        if not count:
            console.print("[dim]The trash is already empty.[/dim]")
            return True
        if not Confirm.ask(f"[bold yellow]Delete {count} item(s) for good?[/bold yellow]", default=False):
            return False
        trash.empty(user, admin, everyone)
        log(f"trash emptied ({count} items)", user=user)
        console.print("[green]Trash emptied.[/green]")
        return True
    if sub in ("restore", "delete") and len(args) >= 2:
        item = trash.find(args[1], user, admin)
        if item is None:
            console.print(f"[bold red]trash: no item '{escape(args[1])}' (see: trash)[/bold red]")
            return False
        try:
            if sub == "restore":
                where = trash.restore(item, args[2] if len(args) > 2 else None)
                log(f"trash restore {item['from']}", user=user)
                console.print(f"[green]Restored {escape(fs.display(where, tilde=True))}[/green]")
            else:
                trash.purge(item)
                log(f"trash delete {item['from']}", user=user)
                console.print(f"[green]Deleted {escape(item['name'])} for good.[/green]")
            return True
        except Exception as e:
            console.print(f"[bold red]trash: {escape(fs.errtext(e))}[/bold red]")
            return False
    console.print(USAGE)
    return False
