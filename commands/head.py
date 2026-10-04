from rich.console import Console
import pyos.fs as fs
import pyos.stdio as stdio

console = Console()
config = {"name": "head", "description": "Show the first lines of a file or piped input (head [-n N] [file])."}


def parse(args):
    n, rest, i = 10, [], 0
    args = list(args or [])
    while i < len(args):
        if args[i] == "-n" and i + 1 < len(args) and args[i + 1].isdigit():
            n, i = int(args[i + 1]), i + 2
        else:
            rest.append(args[i])
            i += 1
    return n, rest


def execute(args=None):
    n, files = parse(args)
    if files:
        try:
            with open(fs.resolve(files[0]), "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except Exception as e:
            console.print(f"[bold red]head: {files[0]}: {e}[/bold red]")
            return
    elif stdio.read_stdin() is not None:
        lines = stdio.read_stdin().splitlines()
    else:
        console.print("[bold red]Usage:[/bold red] head [-n N] <file>")
        return
    for line in lines[:n]:
        console.print(line, markup=False, highlight=False)
