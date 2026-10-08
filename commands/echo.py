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
    if args:
        message = " ".join(args)
    else:
        try:
            message = Prompt.ask("[bold cyan]Enter message to echo:[/bold cyan]", default="")
        except (EOFError, KeyboardInterrupt):                          # nobody to ask (a pipe, a script, an app): an empty line, like echo with nothing
            message = ""
    console.print(message, markup=False, highlight=False)
