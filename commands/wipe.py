from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
import pyos
import core

# Command metadata
config = {
    "name": "wipe",
    "description": "Erases all accounts, files and packages and returns the OS to factory conditions (admins only)."
}

console = Console()


def execute():
    if pyos.userinfo()[1] != "admin":
        console.print("[bold red]You do not have permission to use this command[/bold red]")
        return False
    console.print(Panel.fit("[bold red]WARNING: this erases every account, every user's files and all installed packages![/bold red]", style="red"))
    console.print("[yellow]Tip: back up first with[/yellow] [bold]backup create --system[/bold] [yellow]and copy it somewhere safe (share send).[/yellow]")
    typed = Prompt.ask("Type [bold]WIPE[/bold] to erase everything, or anything else to cancel", default="")
    if typed.strip() != "WIPE":
        console.print("[bold green]Wipe cancelled. Nothing was changed.[/bold green]")
        return False
    from pyos import audit
    if not audit.elevate("erase the whole system (wipe)"):
        console.print("[bold green]Wipe cancelled. Nothing was changed.[/bold green]")
        return False
    core.simulate_shutdown_wipe()
    return True
