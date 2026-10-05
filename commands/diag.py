from rich.console import Console
from rich.markup import escape

import pyos.fs as fs
from core import liveboot

console = Console()
config = {"name": "diag", "description": "Collect a hardware and boot report in a file (diag --show prints it too)."}


def execute(args=None):
    args = list(args or [])
    try:
        path = liveboot.save_diagnostics()
    except OSError as e:
        console.print(f"[bold red]diag: {escape(fs.errtext(e))}[/bold red]")
        return False
    console.print(f"[green]Saved {escape(fs.display(path, tilde=True))}[/green]")
    if "--show" in args:
        console.print(escape(liveboot.diagnostics_text()), highlight=False)
    else:
        console.print("[dim]Read it with cat, copy it with share, or attach it to a problem report (report).[/dim]")
    return True
