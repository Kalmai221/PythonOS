from rich.console import Console
import pyos.fs as fs
import pyos.stdio as stdio

console = Console()
config = {"name": "cat", "description": "Print the contents of a file (cat <file>)."}


def execute(args=None):
    if not args:
        if stdio.read_stdin() is not None:
            console.print(stdio.read_stdin(), markup=False, highlight=False, end="")
        else:
            console.print("[bold red]Usage:[/bold red] cat <file>")
        return
    for name in args:
        try:
            with open(fs.resolve(name), "r", encoding="utf-8", errors="replace") as f:
                console.print(f.read(), markup=False, highlight=False)
        except Exception as e:
            console.print(f"[bold red]cat: {name}: {e}[/bold red]")
