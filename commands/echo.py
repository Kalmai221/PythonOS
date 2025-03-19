# echo.py in commands directory

from rich.console import Console
from rich.prompt import Prompt

# Command metadata
config = {
    "name": "echo",
    "description": "Echoes back any input you provide."
}

console = Console()

def execute():
    message = Prompt.ask("[bold cyan]Enter message to echo:[/bold cyan]", default="")
    console.print(f"[bold yellow]Echo: {message}[/bold yellow]")
