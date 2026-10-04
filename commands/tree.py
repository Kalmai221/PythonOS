import os
from rich.console import Console
import pyos.fs as fs

console = Console()
config = {"name": "tree", "description": "Show a directory tree (tree [path])."}

MAX_ENTRIES = 500


def execute(args=None):
    try:
        root = fs.resolve(args[0]) if args else fs.current_dir()
    except PermissionError as e:
        console.print(f"[bold red]tree: {fs.errtext(e)}[/bold red]")
        return False
    if not os.path.isdir(root):
        console.print("[bold red]tree: not a directory[/bold red]")
        return False

    count = [0]
    console.print(fs.display(root, tilde=True), markup=False)

    def walk(directory, prefix):
        try:
            entries = sorted(os.listdir(directory), key=str.lower)
        except OSError:
            return
        entries = [e for e in entries if not e.startswith(".")]
        for i, name in enumerate(entries):
            if count[0] >= MAX_ENTRIES:
                return
            count[0] += 1
            last = i == len(entries) - 1
            full = os.path.join(directory, name)
            is_dir = os.path.isdir(full)
            console.print(f"{prefix}{'`-- ' if last else '|-- '}{name}{'/' if is_dir else ''}", markup=False, highlight=False)
            if is_dir:
                try:
                    fs._check_permission(full, False)  # skip dirs we may not enter
                except PermissionError:
                    continue
                walk(full, prefix + ("    " if last else "|   "))

    walk(root, "")
    if count[0] >= MAX_ENTRIES:
        console.print(f"... (stopped after {MAX_ENTRIES} entries)", markup=False)
    return True
