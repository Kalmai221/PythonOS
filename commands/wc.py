from rich.console import Console
import pyos.fs as fs
import pyos.stdio as stdio

console = Console()
config = {"name": "wc", "description": "Count lines, words and characters (wc [file])."}


def execute(args=None):
    if args:
        try:
            with open(fs.resolve(args[0]), "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as e:
            console.print(f"[bold red]wc: {args[0]}: {e}[/bold red]")
            return False
    elif stdio.read_stdin() is not None:
        text = stdio.read_stdin()
    else:
        console.print("[bold red]Usage:[/bold red] wc <file>")
        return False
    console.print(f"{text.count(chr(10)):>6} {len(text.split()):>6} {len(text):>6}", markup=False)
    return True
