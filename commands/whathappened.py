from rich.console import Console

from core import whathappened

console = Console()
config = {"name": "whathappened", "description": "Explain why the last session ended badly (power cut, crash) and what it was doing."}


def execute(args=None):
    whathappened.show()
    return True
