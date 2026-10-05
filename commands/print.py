import os
import tempfile

from rich.console import Console
from rich.markup import escape

import pyos
import pyos.fs as fs
from pyos import pdftext
from core import hardware

console = Console()
config = {"name": "print", "description": "Print a file on the default printer (print <file>); text files and PDFs. Set a printer up with: hwsetup printer"}

MAX_BYTES = 5 * 1024 * 1024


def execute(args=None):
    if not args:
        console.print("[bold red]Usage:[/bold red] print <file>")
        return False
    if not hardware.have("lp"):
        console.print("[yellow]Printing is not available here. On the live ISO, set a printer up with: hwsetup printer[/yellow]")
        return False
    try:
        path = fs.resolve(args[0])
        if not os.path.isfile(path):
            raise FileNotFoundError(2, "No such file or directory")
        with open(path, "rb") as f:
            data = f.read(MAX_BYTES + 1)
    except (OSError, PermissionError) as e:
        console.print(f"[bold red]print: {escape(args[0])}: {escape(fs.errtext(e))}[/bold red]")
        return False
    if len(data) > MAX_BYTES:
        console.print("[bold red]print: that file is too large to print here (5 MB limit)[/bold red]")
        return False
    if not data.startswith(b"%PDF"):
        if b"\0" in data:
            console.print("[bold red]print: only text files and PDFs can be printed[/bold red]")
            return False
        data = pdftext.make_pdf(data.decode("utf-8", errors="replace"))
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        name = tmp.name
    try:
        code, out = hardware.run(["lp", name], timeout=60)
    finally:
        try:
            os.remove(name)
        except OSError:
            pass
    if code != 0:
        console.print(f"[bold red]print: {escape(out.strip()[-150:]) or 'the printer did not accept the job'}[/bold red]")
        return False
    console.print(f"[green]Sent {escape(args[0])} to the printer.[/green]")
    return True
