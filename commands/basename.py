from pyos import textcmd

config = {"name": "basename", "description": "The last part of a path (basename <path> [suffix])."}


def base(path, suffix=""):
    name = path.rstrip("/").rsplit("/", 1)[-1] or "/"
    return name[: -len(suffix)] if suffix and name.endswith(suffix) and name != suffix else name


def execute(args=None):
    args = list(args or [])
    if not args:
        textcmd.console.print("[bold red]Usage:[/bold red] basename <path> [suffix]")
        return False
    textcmd.emit(base(args[0].replace("\\", "/"), args[1] if len(args) > 1 else ""))
    return True
