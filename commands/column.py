import shutil

from rich.console import Console

from pyos import textcmd

console = Console()
config = {"name": "column", "description": "Line text up in columns (column [-t] [-s separator] [-o separator] [file]); -t makes a table of the fields."}


def table(lines, separator=None, output="  "):
    """The lines with their fields padded into aligned columns (the last field of a line is not padded)."""
    rows = [(line.split(separator) if separator else line.split()) for line in lines if line.strip()]
    widths = {}
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths.get(i, 0), len(cell))
    return [output.join(cell.ljust(widths[i]) if i < len(row) - 1 else cell for i, cell in enumerate(row)) for row in rows]


def fill(lines, width=80):
    """The lines arranged down the columns that fit in `width` characters, like ls does."""
    items = [line.strip() for line in lines if line.strip()]
    if not items:
        return []
    cell = max(len(i) for i in items) + 2
    per_row = max(1, width // cell)
    height = -(-len(items) // per_row)
    return ["".join(items[r + c * height].ljust(cell) for c in range(per_row) if r + c * height < len(items)).rstrip() for r in range(height)]


def execute(args=None):
    options, files = textcmd.flags(args, with_value="so")
    lines = textcmd.read_lines(files, "column")
    if lines is None:
        return False
    if options.get("t"):
        output = options.get("o") if isinstance(options.get("o"), str) and options.get("o") else "  "
        result = table(lines, options.get("s") if isinstance(options.get("s"), str) and options.get("s") else None, output)
    else:
        result = fill(lines, shutil.get_terminal_size((80, 24)).columns)
    for line in result:
        textcmd.emit(line)
    return True
