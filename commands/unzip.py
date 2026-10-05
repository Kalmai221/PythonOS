from rich.console import Console
from rich.markup import escape
import zipfile
from pyos import archive
import pyos.fs as fs

console = Console()
config = {"name": "unzip", "description": "Unpack a zip archive: unzip [-l] [-o] <archive.zip> [-d folder]"}


def execute(args=None):
    args = list(args or [])
    listing = "-l" in args
    overwrite = "-o" in args
    dest = "."
    if "-d" in args:
        i = args.index("-d")
        if i + 1 >= len(args):
            console.print("[bold red]unzip: -d needs a folder[/bold red]")
            return False
        dest = args[i + 1]
        del args[i:i + 2]
    names = [a for a in args if not a.startswith("-")]
    if len(names) != 1:
        console.print("[bold red]Usage:[/bold red] unzip [-l] [-o] <archive.zip> [-d folder]")
        return False
    try:
        if listing:
            items = archive.list_zip(names[0])
            for name, size in items:
                console.print(f"{size:>10}  {escape(name)}", highlight=False)
            console.print(f"{len(items)} item(s)")
            return True
        count, total = archive.extract_zip(names[0], dest, overwrite)
    except (archive.ArchiveError, OSError, PermissionError, zipfile.BadZipFile) as e:
        console.print(f"[bold red]unzip: {escape(fs.errtext(e) if not isinstance(e, zipfile.BadZipFile) else 'not a zip file')}[/bold red]")
        return False
    console.print(f"Unpacked {count} file(s) ({archive.human(total)}).")
    return True
