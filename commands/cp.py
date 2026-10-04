import os
import shutil
from rich.console import Console
import pyos.fs as fs

console = Console()
config = {"name": "cp", "description": "Copy a file or directory (cp <source> <destination>)."}


def execute(args=None):
    if not args or len(args) != 2:
        console.print("[bold red]Usage:[/bold red] cp <source> <destination>")
        return False
    try:
        src, dst = fs.resolve(args[0]), fs.resolve(args[1], write=True)
        if not os.path.exists(src):
            console.print(f"[bold red]cp: {args[0]}: No such file or directory[/bold red]")
            return False
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, os.path.basename(src)) if os.path.isdir(dst) else dst)
        else:
            shutil.copy2(src, dst)
        return True
    except Exception as e:
        console.print(f"[bold red]cp: {e}[/bold red]")
        return False
