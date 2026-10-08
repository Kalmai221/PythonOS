from rich.console import Console

from pyos import textcmd

console = Console()
config = {"name": "paste", "description": "Join files side by side (paste [-d delimiter] [-s] <file>...)."}


def join(columns, delimiter="\t", serial=False):
    """Lines made from lists of lines: line n of each list side by side, or (serial) each list on a line of its own."""
    if serial:
        return [delimiter.join(column) for column in columns]
    height = max((len(c) for c in columns), default=0)
    return [delimiter.join(c[i] if i < len(c) else "" for c in columns) for i in range(height)]


def execute(args=None):
    options, files = textcmd.flags(args, with_value="d")
    if not files:
        console.print("[bold red]Usage:[/bold red] paste [-d delimiter] [-s] <file>...")
        return False
    delimiter = options.get("d") if isinstance(options.get("d"), str) and options.get("d") != "" else "\t"
    delimiter = delimiter.replace("\\t", "\t").replace("\\n", "\n")
    columns = [textcmd.read_lines([f], "paste") for f in files]
    if None in columns:
        return False
    for line in join(columns, delimiter, bool(options.get("s"))):
        textcmd.emit(line)
    return True
