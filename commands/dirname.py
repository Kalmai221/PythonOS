from pyos import textcmd

config = {"name": "dirname", "description": "The folder part of a path (dirname <path>)."}


def folder(path):
    path = path.rstrip("/")
    if "/" not in path:
        return "." if path else "/"
    return path.rsplit("/", 1)[0] or "/"


def execute(args=None):
    if not args:
        textcmd.console.print("[bold red]Usage:[/bold red] dirname <path>")
        return False
    textcmd.emit(folder(args[0].replace("\\", "/")))
    return True
