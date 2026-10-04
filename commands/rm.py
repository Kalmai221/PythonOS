import os
import shutil
from rich.console import Console
from rich.prompt import Confirm
import pyos.fs as fs

console = Console()
config = {"name": "rm", "description": "Remove files or directories (rm <path>)."}


def execute(args=None):
    if not args:
        console.print("[bold red]Usage:[/bold red] rm <path>")
        return
    for name in args:
        try:
            path = fs.resolve(name, write=True)
            if path == fs.BASE_DIR:
                console.print("[bold red]rm: refusing to remove the root directory.[/bold red]")
            elif os.path.isdir(path):
                if Confirm.ask(f"[bold yellow]'{name}' is a directory. Remove it and everything inside?[/bold yellow]", default=False):
                    shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
            else:
                console.print(f"[bold red]rm: {name}: No such file or directory[/bold red]")
        except Exception as e:
            console.print(f"[bold red]rm: {name}: {e}[/bold red]")
