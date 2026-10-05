import re
from rich.console import Console
import pyos
import pyos.fs as fs

console = Console()
config = {"name": "hostname", "description": "Show the system hostname (admins: hostname <new-name>)."}


def execute(args=None):
    if not args:
        console.print(fs.hostname(), markup=False)
        return True
    if pyos.userinfo()[1] != "admin":
        console.print("[bold red]hostname: Permission denied[/bold red]")
        return False
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", args[0]):
        console.print("[bold red]hostname: invalid name (letters, numbers, '-' and '_', max 32)[/bold red]")
        return False
    with open(fs.resolve("/etc/hostname", write=True), "w") as f:
        f.write(args[0] + "\n")
    pyos.log.log(f"hostname changed to {args[0]}", user=pyos.userinfo()[0])
    if pyos.userinfo()[1] == "admin":
        from pyos import audit
        audit.record("changed the host name", f"to {args[0]}")
    return True
