import os

from rich.console import Console
from rich.markup import escape
from rich.table import Table

import pyos
import pyos.fs as fs
from pyos import filemanager, filemanager_ui, stdio

console = Console()
config = {
    "name": "fm",
    "description": "The file manager: browse, preview, copy, move, rename and delete (fm [folder]).",
    "alias": ["explorer", "filemanager"],
}


def _listing(manager):
    """Where there is no full screen (the Android app, a pipe): the folder as a table, and what to use instead."""
    try:
        items = manager.entries()
    except filemanager.FileManagerError as e:
        console.print(f"[bold red]fm: {escape(str(e))}[/bold red]")
        return False
    table = Table(header_style="bold blue", title=escape(fs.display(manager.cwd, tilde=True)), title_justify="left")
    for column in ("Name", "Size", "Modified"):
        table.add_column(column)
    for e in items:
        table.add_row(("[cyan]" + escape(e.name) + "/[/cyan]") if e.is_dir else escape(e.name), "" if e.is_dir else filemanager.human(e.size), filemanager.when(e.mtime))
    console.print(table)
    console.print("[dim]The full-screen file manager needs a real terminal. Here: ls, cd, cp, mv, rm, mkdir, edit.[/dim]")
    return True


def execute(args=None):
    args = list(args or [])
    user = pyos.userinfo()[0]
    start = None
    if args:
        try:
            start = fs.resolve(args[0])
        except PermissionError as e:
            console.print(f"[bold red]files: {escape(str(e))}[/bold red]")
            return False
        if not os.path.isdir(start):
            console.print(f"[bold red]files: {escape(args[0])}: not a folder[/bold red]")
            return False
    manager = filemanager.Manager(start, user)
    if not filemanager_ui.can_use():
        return _listing(manager)
    stdio.fresh_screen()
    filemanager_ui.run(start, user)
    return True
