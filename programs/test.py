import pyos
from rich.console import Console

console = Console()

config = {
    "name": "test",
    "description": "Used for Testing Purposes"
}

def execute():
    info = pyos.userinfo()
    if info[0] == "Kalmai221":
        pyos.shutdown()
    else:
        console.print("[bold red]You do not have permission to use this command[/bold red]")