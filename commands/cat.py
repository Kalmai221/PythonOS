from rich.console import Console
import pyos.fs as fs
import pyos.stdio as stdio

console = Console()
config = {"name": "cat", "description": "Print the contents of a file (cat <file>)."}


def execute(args=None):
    if not args:
        if stdio.read_stdin() is not None:
            console.print(stdio.read_stdin(), markup=False, highlight=False, end="")
            return True
        console.print("[bold red]Usage:[/bold red] cat <file>")
        return False
    ok = True
    for name in args:
        try:
            with open(fs.resolve(name), "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            # print exactly what is in the file (no extra blank line after a final newline)
            console.print(text, markup=False, highlight=False, end="" if text.endswith("\n") or not text else "\n")
        except Exception as e:
            console.print(f"[bold red]cat: {name}: {fs.errtext(e)}[/bold red]")
            ok = False
    return ok
