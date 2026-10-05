from rich.console import Console
from rich.markup import escape
import tarfile
from pyos import archive
import pyos.fs as fs

console = Console()
config = {"name": "tar", "description": "Make or unpack tar archives: tar -czf a.tgz <paths> | tar -xzf a.tgz [-C folder] | tar -tf a.tar"}

USAGE = ("[bold red]Usage:[/bold red] tar -c[z]f <archive> <paths>...   |   tar -x[z]f <archive> [-C folder] [-o]   |   "
         "tar -t[z]f <archive>")


def execute(args=None):
    args = list(args or [])
    if not args:
        console.print(USAGE)
        return False
    flags = args[0].lstrip("-")
    rest = args[1:]
    if not flags or not set(flags) <= set("cxtzfvo"):
        console.print(USAGE)
        return False
    dest = "."
    overwrite = "o" in flags
    if "-o" in rest:
        rest.remove("-o")
        overwrite = True
    if "-C" in rest:
        i = rest.index("-C")
        if i + 1 >= len(rest):
            console.print("[bold red]tar: -C needs a folder[/bold red]")
            return False
        dest = rest[i + 1]
        del rest[i:i + 2]
    if "f" not in flags or not rest:
        console.print(USAGE)
        return False
    name, paths = rest[0], rest[1:]
    gz = "z" in flags
    try:
        if "c" in flags:
            if not paths:
                console.print(USAGE)
                return False
            count, size = archive.make_tar(name, paths, gz)
            console.print(f"Added {count} item(s) to {escape(name)} ({archive.human(size)}).")
        elif "x" in flags:
            count, total = archive.extract_tar(name, dest, overwrite=overwrite)
            console.print(f"Unpacked {count} file(s) ({archive.human(total)}).")
        elif "t" in flags:
            items = archive.list_tar(name)
            for n, size in items:
                console.print(f"{size:>10}  {escape(n)}", highlight=False)
        else:
            console.print(USAGE)
            return False
    except tarfile.TarError:
        console.print("[bold red]tar: not a readable tar archive[/bold red]")
        return False
    except (archive.ArchiveError, OSError, PermissionError) as e:
        console.print(f"[bold red]tar: {escape(fs.errtext(e))}[/bold red]")
        return False
    return True
