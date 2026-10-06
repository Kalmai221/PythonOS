import datetime
import os

import pyos.fs as fs
from pyos import textcmd

config = {"name": "stat", "description": "Details of a file or folder: size, type, dates (stat <path>)."}


def execute(args=None):
    if not args:
        textcmd.console.print("[bold red]Usage:[/bold red] stat <path>")
        return False
    ok = True
    for name in args:
        try:
            path = fs.resolve(name)
            info = os.stat(path)
        except Exception as e:                                         # noqa: BLE001
            textcmd.console.print(f"[bold red]stat: {name}: {fs.errtext(e)}[/bold red]")
            ok = False
            continue
        kind = "folder" if os.path.isdir(path) else "file"
        when = lambda t: datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")      # noqa: E731
        textcmd.emit(f"  Path: {fs.display(path, tilde=True)}")
        textcmd.emit(f"  Type: {kind}")
        textcmd.emit(f"  Size: {info.st_size} bytes")
        textcmd.emit(f"Changed: {when(info.st_mtime)}")
        textcmd.emit(f"Created: {when(info.st_ctime)}")
    return ok
