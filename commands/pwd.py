from rich.console import Console
import pyos.fs as fs

console = Console()
config = {"name": "pwd", "description": "Print the current directory."}


def execute(args=None):
    console.print(fs.display(fs.current_dir()), markup=False)
