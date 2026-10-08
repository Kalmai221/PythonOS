from rich.console import Console

import pyos.fs as fs
from pyos import gzipfile, textcmd

console = Console()
config = {"name": "zcat", "description": "Show the text inside a gzip file without unpacking it (zcat <file.gz>)."}


def execute(args=None):
    files = [a for a in (args or []) if not a.startswith("-")]
    if len(files) != 1:
        console.print("[bold red]Usage:[/bold red] zcat <file.gz>")
        return False
    try:
        data = gzipfile.read_limited(fs.resolve(files[0]))
    except (gzipfile.GzipError, OSError) as e:
        console.print(f"[bold red]zcat: {fs.errtext(e) if isinstance(e, OSError) else e}[/bold red]")
        return False
    from pyos import textfile
    text = textfile.decode(data)[0]
    console.print(text, markup=False, highlight=False, end="" if text.endswith("\n") or not text else "\n")
    return True
