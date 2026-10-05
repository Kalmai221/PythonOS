import os
import shutil

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm

import pyos
import pyos.fs as fs
from pyos import settings, trash
from pyos.i18n import tr
from pyos.log import log

console = Console()
config = {"name": "rm", "description": "Remove files or folders (rm [-f] [-P] <path>...). They go to the trash: undo brings the last one back."}


def execute(args=None):
    args = list(args or [])
    force = any(a in ("-f", "-rf", "-fr") for a in args)
    permanent = any(a in ("-P", "--purge", "-rP", "-Pr") for a in args)
    names = [a for a in args if not a.startswith("-")]
    if not names:
        console.print("[bold red]Usage:[/bold red] rm \\[-f] \\[-P] <path>...   (-P deletes for good instead of using the trash)")
        return False
    user, _role = pyos.userinfo()
    use_trash = trash.enabled() and not permanent
    ok, moved = True, 0
    for name in names:
        try:
            path = fs.resolve(name, write=True)
            if path == fs.BASE_DIR:
                console.print("[bold red]rm: refusing to remove the root directory.[/bold red]")
                ok = False
                continue
            if not os.path.lexists(path):
                if not force:
                    console.print(f"[bold red]rm: {escape(name)}: No such file or directory[/bold red]")
                    ok = False
                continue
            if os.path.isdir(path) and not (force or not settings.get("confirm_delete") or Confirm.ask(
                    f"[bold yellow]'{escape(name)}' is a directory. Remove it and everything inside?[/bold yellow]", default=False)):
                ok = False
                continue
            if use_trash:
                item = trash.discard(path, user)
                if item is not None:
                    moved += 1
                    log(f"rm {item['from']} (to trash)", user=user)
                    continue
                console.print(f"[yellow]rm: {escape(name)} is too big for the trash.[/yellow]")
                if not Confirm.ask("Delete it for good?", default=False):
                    ok = False
                    continue
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            log(f"rm {fs.display(path)} (permanent)", user=user)
        except Exception as e:
            console.print(f"[bold red]rm: {escape(name)}: {escape(fs.errtext(e))}[/bold red]")
            ok = False
    if moved:
        console.print("[dim]" + escape(tr("{n} item(s) moved to the trash - 'undo' brings the last one back, 'trash' lists them.", n=moved)) + "[/dim]")
    return ok
