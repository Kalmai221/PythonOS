import getpass
from rich.console import Console
from rich.markup import escape
import pyos
import pyos.fs as fs
import users

console = Console()
config = {"name": "su", "description": "Work as another user: su <user>. Admins need no password; type exit to come back."}


def execute(args=None):
    if not args:
        console.print("[bold red]Usage:[/bold red] su <user>")
        return False
    target = args[0]
    me, role = pyos.userinfo()
    if not me:
        console.print("[bold red]su: you are not logged in.[/bold red]")
        return False
    accounts = users.get_users()
    if target not in accounts:
        console.print(f"[bold red]su: no such user: {escape(target)}[/bold red]")
        return False
    if target == me:
        console.print("[yellow]You already are that user.[/yellow]")
        return True

    if role != "admin":                                        # admins are trusted like root; others must know the password
        try:
            ok, message = users.authenticate(target, getpass.getpass(f"Password for {target}: "))
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled.[/yellow]")
            return False
        if not ok:
            console.print(f"[bold red]su: {escape(message)}[/bold red]")
            return False

    if role == "admin":
        from pyos import audit
        if not audit.elevate(f"work as '{target}'"):
            return False
    import shell
    previous_dir = fs.current_dir()
    pyos.log.log(f"su to {target}", "WARN", user=me)
    users.save_session(target, accounts[target]["role"])
    console.print(f"[dim]Now working as {escape(target)}. Type exit to return to {escape(me)}.[/dim]")
    try:
        shell.start_shell(target)
    finally:
        users.save_session(me, role)
        fs.save_current_dir(previous_dir)
        pyos.log.log(f"back from su {target}", user=me)
    console.print(f"[dim]Back as {escape(me)}.[/dim]")
    return True
