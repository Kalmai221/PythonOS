#!/usr/bin/env python3
"""Hash and encoding tool: checksums (MD5, SHA-1, SHA-256, SHA-512, ...) of text or a file, checking a file against a checksum you were
given, and converting text to and from Base64, URL encoding, hexadecimal, binary and HTML entities.
Usage: hashtool hash <text>  |  hashtool file <path> [checksum]  |  hashtool encode <kind> <text>  |  hashtool decode <kind> <text>
(no arguments opens a menu). Kinds: base64, url, hex, binary, html."""
import base64
import binascii
import hashlib
import html
import sys
import urllib.parse

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

try:
    from pyos import fs
except ImportError:
    fs = None

console = Console()
ALGORITHMS = ["md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_256", "blake2b"]
MAX_FILE = 2 * 1024 ** 3


def hash_bytes(data, algorithms=ALGORITHMS):
    return {a: hashlib.new(a, data).hexdigest() for a in algorithms}


def hash_file(path, algorithms=ALGORITHMS):
    hashers = {a: hashlib.new(a) for a in algorithms}
    size = 0
    with open(fs.resolve(path) if fs else path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE:
                raise ValueError("that file is too large (2 GB limit)")
            for h in hashers.values():
                h.update(chunk)
    return {a: h.hexdigest() for a, h in hashers.items()}, size


def encode(kind, text):
    data = text.encode("utf-8")
    if kind == "base64":
        return base64.b64encode(data).decode()
    if kind == "url":
        return urllib.parse.quote(text, safe="")
    if kind == "hex":
        return data.hex()
    if kind == "binary":
        return " ".join(format(b, "08b") for b in data)
    if kind == "html":
        return html.escape(text, quote=True)
    raise ValueError(f"unknown kind '{kind}' (base64, url, hex, binary, html)")


def decode(kind, text):
    try:
        if kind == "base64":
            padded = text.strip() + "=" * (-len(text.strip()) % 4)
            return base64.b64decode(padded, validate=True).decode("utf-8", errors="replace")
        if kind == "url":
            return urllib.parse.unquote(text)
        if kind == "hex":
            return bytes.fromhex(text.replace(" ", "").replace("0x", "")).decode("utf-8", errors="replace")
        if kind == "binary":
            return bytes(int(b, 2) for b in text.split()).decode("utf-8", errors="replace")
        if kind == "html":
            return html.unescape(text)
    except (ValueError, binascii.Error) as e:
        raise ValueError(f"that is not valid {kind}: {e}") from None
    raise ValueError(f"unknown kind '{kind}' (base64, url, hex, binary, html)")


def identify(checksum):
    """Which algorithms produce a checksum of this length?"""
    n = len(checksum.strip())
    return [a for a, d in {"md5": 32, "sha1": 40, "sha224": 56, "sha256": 64, "sha384": 96, "sha512": 128}.items() if d == n]


def show_hashes(hashes):
    table = Table(show_header=False, box=None)
    for name, digest in hashes.items():
        table.add_row(f"[cyan]{name}[/cyan]", digest)
    console.print(table)


def verify(path, expected):
    expected = expected.strip().lower()
    algorithms = identify(expected)
    if not algorithms:
        console.print("[yellow]I cannot tell which algorithm that checksum is from (its length is unusual).[/yellow]")
        return False
    hashes, _ = hash_file(path, algorithms)
    if any(h == expected for h in hashes.values()):
        console.print("[bold green]Match: the file is exactly what the checksum describes.[/bold green]")
        return True
    console.print("[bold red]The checksum does NOT match - the file is different or damaged.[/bold red]")
    return False


def main(args):
    if args and args[0] == "hash" and len(args) > 1:
        show_hashes(hash_bytes(" ".join(args[1:]).encode("utf-8")))
    elif args and args[0] == "file" and len(args) > 1:
        if len(args) > 2:
            verify(args[1], args[2])
        else:
            hashes, size = hash_file(args[1])
            show_hashes(hashes)
            console.print(f"[dim]{size} bytes[/dim]")
    elif args and args[0] in ("encode", "decode") and len(args) > 2:
        console.print((encode if args[0] == "encode" else decode)(args[1].lower(), " ".join(args[2:])), markup=False, highlight=False)
    elif args:
        console.print("hashtool [hash <text> | file <path> [checksum] | encode <kind> <text> | decode <kind> <text>]  kinds: base64 url hex binary html")
    else:
        while True:
            choice = Prompt.ask("(h)ash text, hash a (f)ile, (v)erify a file, (e)ncode, (d)ecode, (q)uit", choices=["h", "f", "v", "e", "d", "q"], default="h")
            try:
                if choice == "q":
                    return
                if choice == "h":
                    show_hashes(hash_bytes(Prompt.ask("Text").encode("utf-8")))
                elif choice == "f":
                    hashes, size = hash_file(Prompt.ask("File"))
                    show_hashes(hashes)
                    console.print(f"[dim]{size} bytes[/dim]")
                elif choice == "v":
                    verify(Prompt.ask("File"), Prompt.ask("Checksum you were given"))
                else:
                    kind = Prompt.ask("Kind", choices=["base64", "url", "hex", "binary", "html"], default="base64")
                    text = Prompt.ask("Text")
                    console.print((encode if choice == "e" else decode)(kind, text), markup=False, highlight=False)
            except (OSError, ValueError, PermissionError) as e:
                console.print(f"[red]{escape(fs.errtext(e) if fs and isinstance(e, OSError) else str(e))}[/red]")


def execute(args=None):
    try:
        main(list(args or []))
    except (OSError, ValueError, PermissionError) as e:
        console.print(f"[red]{escape(fs.errtext(e) if fs and isinstance(e, OSError) else str(e))}[/red]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
