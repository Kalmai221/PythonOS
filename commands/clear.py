# ping.py in commands directory
import os
from rich.console import Console

config = {
    "name": "clear",
    "description": "Clears the terminal"
}

console = Console()

def execute():
    os.system("clear")
    