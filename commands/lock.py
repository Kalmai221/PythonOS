from rich.console import Console
import pyos

console = Console()
config = {"name": "lock", "description": "Lock the session until your password is entered again (see settings: auto_lock_minutes)."}


def execute(args=None):
    user = pyos.userinfo()[0]
    if not user:
        console.print("[bold red]lock: you are not logged in.[/bold red]")
        return False
    import shell
    if shell.lock_session(user):
        return True
    console.print("[bold red]Logging out.[/bold red]")
    raise shell.ExitShell
