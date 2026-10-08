# pyos/checksum.py - md5sum, sha1sum, sha256sum and sha512sum: the same work with a different hash
#
#   <name>sum file...        prints "hash  file" for each file (or for the piped text when there is no file)
#   <name>sum -c list        reads lines of "hash  file" (what the command printed earlier) and says OK or FAILED for each
# MD5 and SHA-1 are broken as protection against someone who wants to forge a file; they are still fine to spot a damaged download.
import hashlib
import hmac

from rich.console import Console

import pyos.fs as fs
import pyos.stdio as stdio
from pyos import textcmd

console = Console()
CHUNK = 1 << 20


def digest_file(name, algorithm):
    """The hex digest of a file inside the PythonOS filesystem rules."""
    h = hashlib.new(algorithm)
    with open(fs.resolve(name), "rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def digest_text(text, algorithm):
    return hashlib.new(algorithm, text.encode("utf-8")).hexdigest()


def parse_line(line):
    """(hash, file name) from 'hash  file' or 'hash *file', or None."""
    parts = line.strip().split(None, 1)
    if len(parts) != 2 or not all(c in "0123456789abcdefABCDEF" for c in parts[0]):
        return None
    return parts[0].lower(), parts[1].lstrip("*").strip()


def run(command, algorithm, args):
    options, files = textcmd.flags(args, with_value="")
    if options.get("c"):
        return check(command, algorithm, files)
    if not files:
        piped = stdio.read_stdin()
        if piped is None:
            console.print(f"[bold red]Usage:[/bold red] {command} <file>...   |   {command} -c <list>   |   text | {command}")
            return False
        textcmd.emit(f"{digest_text(piped, algorithm)}  -")
        return True
    ok = True
    for name in files:
        try:
            textcmd.emit(f"{digest_file(name, algorithm)}  {name}")
        except Exception as e:                                       # noqa: BLE001 - say it the way every command does
            console.print(f"[bold red]{command}: {name}: {fs.errtext(e)}[/bold red]")
            ok = False
    return ok


def check(command, algorithm, files):
    if len(files) != 1:
        console.print(f"[bold red]Usage:[/bold red] {command} -c <list of 'hash  file' lines>")
        return False
    lines = textcmd.read_lines(files, command)
    if lines is None:
        return False
    good = bad = 0
    for line in lines:
        if not line.strip():
            continue
        parsed = parse_line(line)
        if parsed is None:
            console.print(f"[yellow]{command}: skipped a line that is not 'hash  file': {line[:40]}[/yellow]")
            continue
        expected, name = parsed
        try:
            actual = digest_file(name, algorithm)
        except Exception as e:                                       # noqa: BLE001
            textcmd.emit(f"{name}: FAILED to read ({fs.errtext(e)})")
            bad += 1
            continue
        if hmac.compare_digest(actual, expected):
            textcmd.emit(f"{name}: OK")
            good += 1
        else:
            textcmd.emit(f"{name}: FAILED")
            bad += 1
    if bad:
        console.print(f"[bold red]{command}: {bad} of {good + bad} checksum(s) did NOT match[/bold red]")
    return bad == 0 and good > 0
