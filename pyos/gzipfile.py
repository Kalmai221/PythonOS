# pyos/gzipfile.py - gzip, gunzip and zcat: one file in, one file out
#
# Files are read and written through the PythonOS filesystem rules (pyos.fs.resolve), and unpacking stops at the same size limit as zip and tar so that a
# tiny file cannot fill the disk (a "gzip bomb").
import gzip
import os
import shutil

from rich.console import Console
from rich.markup import escape

from . import archive, fs, textcmd

console = Console()

CHUNK = 1 << 20


class GzipError(Exception):
    """A problem to tell the person about (not a crash)."""


def compress(name, keep=False, level=6):
    """Make <name>.gz next to a file and (unless keep) remove the original. Returns (new name, size before, size after)."""
    source = fs.resolve(name)
    if not os.path.isfile(source):
        raise GzipError(f"{name} is not a file")
    if name.endswith(".gz"):
        raise GzipError(f"{name} already ends in .gz")
    target_name = name + ".gz"
    target = fs.resolve(target_name, write=True)
    if os.path.exists(target):
        raise GzipError(f"{target_name} already exists")
    with open(source, "rb") as src, gzip.open(target, "wb", compresslevel=level) as out:
        shutil.copyfileobj(src, out, CHUNK)
    before, after = os.path.getsize(source), os.path.getsize(target)
    if not keep:
        os.remove(source)
    return target_name, before, after


def read_limited(source):
    """The bytes inside a .gz file (at most the zip and tar limit). Raises GzipError."""
    chunks, total = [], 0
    try:
        with gzip.open(source, "rb") as f:
            while True:
                block = f.read(CHUNK)
                if not block:
                    break
                total += len(block)
                if total > archive.MAX_TOTAL:
                    raise GzipError("the file is too large to unpack here")
                chunks.append(block)
    except (OSError, EOFError) as e:
        if isinstance(e, GzipError):
            raise
        if isinstance(e, PermissionError) or isinstance(e, FileNotFoundError):
            raise
        raise GzipError("not a readable gzip file") from None
    return b"".join(chunks)


def decompress_file(name, keep=False):
    """Unpack <name>.gz next to itself and (unless keep) remove the .gz. Returns (new name, size before, size after)."""
    if not name.endswith(".gz"):
        raise GzipError(f"{name} does not end in .gz")
    source = fs.resolve(name)
    data = read_limited(source)
    target_name = name[:-3]
    target = fs.resolve(target_name, write=True)
    if os.path.exists(target):
        raise GzipError(f"{target_name} already exists")
    with open(target, "wb") as out:
        out.write(data)
    before = os.path.getsize(source)
    if not keep:
        os.remove(source)
    return target_name, before, len(data)


def run(command, args, decompress=False):
    """The gzip, gunzip commands: gzip [-k] [-d] file...  Returns True when every file worked."""
    options, files = textcmd.flags(args)
    if not files:
        console.print(f"[bold red]Usage:[/bold red] {command} [-k]{'' if decompress else ' [-d]'} <file>...")
        return False
    ok = True
    for name in files:
        try:
            if decompress or options.get("d"):
                new, before, after = decompress_file(name, bool(options.get("k")))
            else:
                new, before, after = compress(name, bool(options.get("k")))
        except (GzipError, OSError) as e:
            console.print(f"[bold red]{command}: {escape(fs.errtext(e) if isinstance(e, OSError) else str(e))}[/bold red]")
            ok = False
            continue
        console.print(f"{escape(name)} -> {escape(new)}  [dim]({archive.human(before)} -> {archive.human(after)})[/dim]")
    return ok
