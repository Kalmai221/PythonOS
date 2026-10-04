import os
import shutil
from rich.console import Console
import pyos.fs as fs

console = Console()
config = {"name": "mv", "description": "Move or rename a file or directory (mv <source> <destination>)."}


def execute(args=None):
    if not args or len(args) != 2:
        console.print("[bold red]Usage:[/bold red] mv <source> <destination>")
        return False
    try:
        src, dst = fs.resolve(args[0], write=True), fs.resolve(args[1], write=True)
        if src == fs.BASE_DIR:
            console.print("[bold red]mv: cannot move the root directory.[/bold red]")
            return False
        if not os.path.exists(src):
            console.print(f"[bold red]mv: {args[0]}: No such file or directory[/bold red]")
            return False
        shutil.move(src, dst)
        return True
    except Exception as e:
        console.print(f"[bold red]mv: {e}[/bold red]")
        return False
