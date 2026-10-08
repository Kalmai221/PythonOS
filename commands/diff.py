import difflib

from rich.console import Console
from rich.markup import escape

import pyos.fs as fs
from pyos import textfile

console = Console()
config = {"name": "diff", "description": "Compare two files line by line: diff [-u] [-q] <file1> <file2>. Exit status says whether they differ."}

MAX_FILE = 5 * 1024 * 1024


def read(name):
    text = textfile.read(name, MAX_FILE + 1)[0]
    if len(text) > MAX_FILE:
        raise ValueError("file is too big to compare (over 5 MB)")
    return text.splitlines()


def execute(args=None):
    args = list(args or [])
    brief = "-q" in args
    unified = "-u" in args
    names = [a for a in args if a not in ("-q", "-u")]
    if len(names) != 2:
        console.print("[bold red]Usage:[/bold red] diff \\[-u] \\[-q] <file1> <file2>")
        return False
    try:
        a, b = read(names[0]), read(names[1])
    except Exception as e:
        console.print(f"[bold red]diff: {escape(fs.errtext(e))}[/bold red]")
        return False
    if a == b:
        return True                                    # identical: silent, like diff
    if brief:
        console.print(f"Files {names[0]} and {names[1]} differ", markup=False)
        return False
    if unified:
        for line in difflib.unified_diff(a, b, names[0], names[1], lineterm=""):
            colour = "green" if line.startswith("+") and not line.startswith("+++") else "red" if line.startswith("-") and not line.startswith("---") else "cyan" if line.startswith("@@") else None
            console.print(f"[{colour}]{escape(line)}[/{colour}]" if colour else escape(line), highlight=False)
        return False
    # classic normal format: 3c3 / < old / --- / > new
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        left = f"{i1 + 1},{i2}" if i2 - i1 > 1 else f"{i1 + 1}" if i2 > i1 else f"{i1}"
        right = f"{j1 + 1},{j2}" if j2 - j1 > 1 else f"{j1 + 1}" if j2 > j1 else f"{j1}"
        kind = {"replace": "c", "delete": "d", "insert": "a"}[tag]
        console.print(f"{left}{kind}{right}", markup=False)
        for line in a[i1:i2]:
            console.print(f"[red]< {escape(line)}[/red]", highlight=False)
        if tag == "replace":
            console.print("---", markup=False)
        for line in b[j1:j2]:
            console.print(f"[green]> {escape(line)}[/green]", highlight=False)
    return False
