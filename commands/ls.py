import os
from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.columns import Columns
from rich.markup import escape
import datetime
import pyos.fs as fs

console = Console()

# Metadata dictionary for commands
config = {
    "name": "ls",
    "description": "List files and folders (ls [-a] [-l] [path])"
}


def _human(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def execute(args=None):
    """Lists files and directories in the current (or given) directory."""
    args = args or []
    show_hidden = "-a" in args
    paths = [a for a in args if not a.startswith("-")]
    try:
        directory = fs.resolve(paths[0]) if paths else fs.current_dir()
        if not os.path.isdir(directory):
            console.print(f"[bold red]Error:[/bold red] {fs.display(directory)} is not a valid directory.")
            return

        items = sorted(os.listdir(directory), key=str.lower)
        if not show_hidden:
            items = [i for i in items if not i.startswith(".")]
        if not items:
            console.print("[bold yellow]Directory is empty.[/bold yellow]")
            return

        if "-l" in args:
            table = Table(box=None, header_style="bold", pad_edge=False)
            table.add_column("Name")
            table.add_column("Size", justify="right")
            table.add_column("Modified", style="dim")
            for item in items:
                full = os.path.join(directory, item)
                st = os.stat(full)
                is_dir = os.path.isdir(full)
                name = f"[bold blue]{escape(item)}/[/bold blue]" if is_dir else escape(item)
                size = "-" if is_dir else _human(st.st_size)
                table.add_row(name, size, datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"))
            console.print(table)
        else:
            cells = [Text(i + "/", style="bold blue") if os.path.isdir(os.path.join(directory, i)) else Text(i)
                     for i in items]
            console.print(Columns(cells, padding=(0, 2), column_first=True))
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
