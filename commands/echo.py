# echo.py in commands directory
from rich.console import Console
from rich.prompt import Prompt

# Command metadata
config = {
    "name": "echo",
    "description": "Echoes back any input you provide (echo <text>)."
}

console = Console()


def execute(args=None):
    message = " ".join(args) if args else Prompt.ask("[bold cyan]Enter message to echo:[/bold cyan]", default="")
    console.print(message, markup=False, highlight=False)
