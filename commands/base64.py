import base64 as codec
import binascii

from rich.console import Console

import pyos.fs as fs
import pyos.stdio as stdio
from pyos import textcmd

console = Console()
config = {"name": "base64", "description": "Encode or decode base64 (base64 [-d] [-w columns] [file])."}


def source_bytes(files):
    """The bytes to work on: the first file, else the piped text. None (after saying why) when there is neither."""
    if files:
        try:
            with open(fs.resolve(files[0]), "rb") as f:
                return f.read()
        except Exception as e:                                         # noqa: BLE001 - say it the way every command does
            console.print(f"[bold red]base64: {files[0]}: {fs.errtext(e)}[/bold red]")
            return None
    piped = stdio.read_stdin()
    if piped is None:
        console.print("[bold red]Usage:[/bold red] base64 [-d] [-w columns] <file>   |   text | base64")
        return None
    return piped.encode("utf-8")


def encode(data, width=76):
    """Base64 lines (wrapped at `width` characters; 0 means one line)."""
    text = codec.b64encode(data).decode("ascii")
    return [text[i:i + width] for i in range(0, len(text), width)] if width else [text]


def decode(text):
    """The bytes for base64 text (spaces and line breaks are ignored). Raises ValueError."""
    cleaned = "".join(text.split())
    try:
        return codec.b64decode(cleaned + "=" * (-len(cleaned) % 4), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("that is not valid base64") from None


def execute(args=None):
    options, files = textcmd.flags(args, with_value="w")
    data = source_bytes(files)
    if data is None:
        return False
    if options.get("d"):
        try:
            raw = decode(data.decode("utf-8", errors="replace"))
        except ValueError as e:
            console.print(f"[bold red]base64: {e}[/bold red]")
            return False
        try:
            textcmd.emit(raw.decode("utf-8").rstrip("\n"))
        except UnicodeDecodeError:
            console.print(f"[yellow]base64: that is {len(raw)} bytes of data that is not text, so it is not shown[/yellow]")
            return False
        return True
    try:
        width = int(options.get("w") or 76)
    except ValueError:
        console.print("[bold red]base64: -w needs a number[/bold red]")
        return False
    for line in encode(data, max(0, width)):
        textcmd.emit(line)
    return True
