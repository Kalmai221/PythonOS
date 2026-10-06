from rich.console import Console

from pyos import archinfo

console = Console()
config = {"name": "arch", "description": "Show the processor family of this computer (x86_64, arm64, ...)."}


def execute(args=None):
    console.print(archinfo.arch(), markup=False, highlight=False)
    return True
