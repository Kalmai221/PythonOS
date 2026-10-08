from rich.console import Console
from rich.markup import escape
import zipfile
from pyos import archive
import pyos.fs as fs

console = Console()
config = {"name": "zip", "description": "Make a zip archive: zip <archive.zip> <file or folder>... (a name ending in .7z makes a 7z archive when py7zr is installed)"}


def execute(args=None):
    if not args or len(args) < 2:
        console.print("[bold red]Usage:[/bold red] zip <archive.zip> <file or folder>...")
        return False
    name = args[0] if args[0].lower().endswith((".zip", ".7z")) else args[0] + ".zip"
    try:
        count, size = (archive.make_7z if archive.is_7z(name) else archive.make_zip)(name, args[1:])
    except (archive.ArchiveError, OSError, PermissionError, zipfile.BadZipFile) as e:
        console.print(f"[bold red]zip: {escape(fs.errtext(e))}[/bold red]")
        return False
    console.print(f"Added {count} item(s) to {escape(name)} ({archive.human(size)}).")
    return True
