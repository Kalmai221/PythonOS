from rich.console import Console

from pyos import textcmd

console = Console()
config = {"name": "comm", "description": "Compare two sorted files line by line (comm [-1] [-2] [-3] <file1> <file2>)."}


def compare(first, second):
    """[(column, line)] where column 1 is only in the first list, 2 only in the second, 3 in both. Both lists must be sorted."""
    result, i, j = [], 0, 0
    while i < len(first) and j < len(second):
        if first[i] == second[j]:
            result.append((3, first[i]))
            i += 1
            j += 1
        elif first[i] < second[j]:
            result.append((1, first[i]))
            i += 1
        else:
            result.append((2, second[j]))
            j += 1
    result.extend((1, line) for line in first[i:])
    result.extend((2, line) for line in second[j:])
    return result


def execute(args=None):
    args = list(args or [])
    hidden = {int(c) for a in args if a.startswith("-") and a[1:] and set(a[1:]) <= set("123") for c in a[1:]}        # -1, -2, -3, -12, -23, -123
    files = [a for a in args if not (a.startswith("-") and a[1:] and set(a[1:]) <= set("123"))]
    if len(files) != 2:
        console.print("[bold red]Usage:[/bold red] comm [-1] [-2] [-3] <file1> <file2>   (-1 hides lines only in the first, -2 only in the second, -3 in both)")
        return False
    lines = [textcmd.read_lines([f], "comm") for f in files]
    if None in lines:
        return False
    shown = [n for n in (1, 2, 3) if n not in hidden]
    for column, line in compare(*lines):
        if column in hidden:
            continue
        textcmd.emit("\t" * shown.index(column) + line)
    return True
