import os

from rich.console import Console

console = Console()
config = {"name": "nproc", "description": "Show how many processor cores there are."}


def execute(args=None):
    console.print(str(os.cpu_count() or 1))
    return True
