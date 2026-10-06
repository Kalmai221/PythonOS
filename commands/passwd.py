import getpass
from rich.console import Console
from rich.markup import escape
import pyos
import users

console = Console()
config = {"name": "passwd", "description": "Change a password: passwd (yours) or, for admins, passwd <user>."}


def execute(args=None):
    args = list(args or [])
    me, role = pyos.userinfo()
    if not me:
        console.print("[bold red]passwd: you are not logged in.[/bold red]")
        return False
    target = args[0] if args else me
    accounts = users.get_users()
    if target not in accounts:
        console.print(f"[bold red]passwd: no such user: {escape(target)}[/bold red]")
        return False
    if target != me and role != "admin":
        console.print("[bold red]passwd: only admins can change someone else's password.[/bold red]")
        return False

    if target != me:
        from pyos import audit
        if not audit.elevate(f"change the password of '{target}'"):
            return False
    try:
        if target == me:
            ok, message = users.authenticate(me, getpass.getpass("Current password: "))
            if not ok:
                console.print(f"[bold red]{escape(message)}[/bold red]")
                return False
        new = getpass.getpass(f"New password for {target}: ")
        problem = users.validate_password(new, target)
        if problem:
            console.print(f"[bold red]{problem}[/bold red]")
            return False
        from pyos import passwords
        note = passwords.advice(new, target)
        if note:
            console.print(f"[yellow]{escape(note)}[/yellow]")
        if getpass.getpass("Confirm new password: ") != new:
            console.print("[bold red]Passwords do not match.[/bold red]")
            return False
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return False

    accounts = users.get_users()
    accounts[target]["password"] = users.hash_password(new)
    users.save_users(accounts)
    pyos.log.log(f"password changed for {target}", "WARN" if target != me else "INFO", user=me)
    console.print(f"[green]Password for {escape(target)} changed.[/green]")
    return True
