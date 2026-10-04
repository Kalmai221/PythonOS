import os
import shutil
from rich.console import Console
from rich.prompt import Confirm
import pyos.fs as fs
from pyos import settings

console = Console()
config = {"name": "rm", "description": "Remove files or directories (rm [-f] <path>...). Folders ask first unless -f or the confirm_delete setting is off."}


def execute(args=None):
    args = list(args or [])
    force = "-f" in args or "-rf" in args or "-fr" in args
    names = [a for a in args if not a.startswith("-")]
    if not names:
        console.print("[bold red]Usage:[/bold red] rm \\[-f] <path>...")
        return False
    ok = True
    for name in names:
        try:
            path = fs.resolve(name, write=True)
            if path == fs.BASE_DIR:
                console.print("[bold red]rm: refusing to remove the root directory.[/bold red]")
                ok = False
            elif os.path.isdir(path):
                if force or not settings.get("confirm_delete") or Confirm.ask(
                        f"[bold yellow]'{name}' is a directory. Remove it and everything inside?[/bold yellow]", default=False):
                    shutil.rmtree(path)
                else:
                    ok = False
            elif os.path.exists(path):
                os.remove(path)
            elif not force:
                console.print(f"[bold red]rm: {name}: No such file or directory[/bold red]")
                ok = False
        except Exception as e:
            console.print(f"[bold red]rm: {name}: {fs.errtext(e)}[/bold red]")
            ok = False
    return ok
