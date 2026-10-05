from rich.console import Console
from rich.markup import escape
import zipfile
from pyos import archive
import pyos.fs as fs

console = Console()
config = {"name": "zip", "description": "Make a zip archive: zip <archive.zip> <file or folder>..."}


def execute(args=None):
    if not args or len(args) < 2:
        console.print("[bold red]Usage:[/bold red] zip <archive.zip> <file or folder>...")
        return False
    name = args[0] if args[0].lower().endswith(".zip") else args[0] + ".zip"
    try:
        count, size = archive.make_zip(name, args[1:])
    except (archive.ArchiveError, OSError, PermissionError, zipfile.BadZipFile) as e:
        console.print(f"[bold red]zip: {escape(fs.errtext(e))}[/bold red]")
        return False
    console.print(f"Added {count} item(s) to {escape(name)} ({archive.human(size)}).")
    return True
