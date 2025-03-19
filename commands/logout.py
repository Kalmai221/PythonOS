from rich.console import Console
import pyos
import time

# Command metadata
config = {
    "name": "logout",
    "description": "Logs you out of your account"
}

console = Console()

def execute():
    pyos.system("clear")
    console.print("[bold yellow]Logging you out of your account...[/bold yellow]")
    time.sleep(2)
    pyos.logout()