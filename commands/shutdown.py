import pyos
from rich.console import Console

console = Console()

config = {
    "name": "shutdown",
    "description": "Initiates the shutdown of the OS"
}

def execute():
    pyos.shutdown()