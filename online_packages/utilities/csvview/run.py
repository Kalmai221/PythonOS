#!/usr/bin/env python3
"""CSV viewer: look at a CSV file without a spreadsheet.

    csvview data.csv
    csvview data.csv --sort price --desc       sort by a column (--desc for biggest first)
    csvview data.csv --filter paris            only rows containing a word
    csvview data.csv --cols name,price         only these columns
    csvview data.csv --rows 50                 show 50 rows (20 by default)
    csvview data.csv --stats                   count, minimum, maximum, average and total of the number columns
"""
import csv
import io
import os
import re
import sys

from rich.console import Console
from rich.table import Table

try:
    from pyos import fs
except ImportError:                                        # run on its own, outside PythonOS
    fs = None

console = Console()
LIMIT = 50_000_000


def read_table(text):
    """(header, rows) from CSV text. The delimiter (comma, semicolon, tab, pipe) is detected."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        return [], []
    header = [h.strip() or f"col{i + 1}" for i, h in enumerate(rows[0])]
    body = [r + [""] * (len(header) - len(r)) if len(r) < len(header) else r for r in rows[1:]]
    return header, body


def number(text):
    """The value of a cell that holds a number ('1,234.50', '2,5', '$10', '45%'), else None."""
    cleaned = text.replace("$", "").replace("%", "").replace(" ", "").strip()
    if "," in cleaned and "." not in cleaned and not re.fullmatch(r"-?\d{1,3}(,\d{3})+", cleaned):
        cleaned = cleaned.replace(",", ".")                 # a decimal comma
    try:
        return float(cleaned.replace(",", ""))
    except ValueError:
        return None


def column_index(header, name):
    lowered = [h.lower() for h in header]
    if name.lower() in lowered:
        return lowered.index(name.lower())
    if name.isdigit() and 1 <= int(name) <= len(header):
        return int(name) - 1
    return None


def sort_rows(rows, index, descending=False):
    """Rows sorted by a column: numbers by value, everything else as text (empty cells last)."""
    def key(row):
        cell = row[index] if index < len(row) else ""
        value = number(cell)
        return (0, value, "") if value is not None else (1, 0.0, cell.lower()) if cell else (2, 0.0, "")
    ordered = sorted(rows, key=key)
    if descending:
        present = [r for r in ordered if key(r)[0] != 2]
        return list(reversed(present)) + [r for r in ordered if key(r)[0] == 2]
    return ordered


def stats(header, rows):
    """[(column, count, minimum, maximum, average, total)] for the columns where most cells are numbers."""
    out = []
    for i, name in enumerate(header):
        values = [number(r[i]) for r in rows if i < len(r) and r[i].strip()]
        numbers = [v for v in values if v is not None]
        if values and len(numbers) >= 0.8 * len(values):
            out.append((name, len(numbers), min(numbers), max(numbers), sum(numbers) / len(numbers), sum(numbers)))
    return out


def execute(args=None):
    args = list(args or [])
    options = {"--sort": None, "--filter": None, "--cols": None, "--rows": "20"}
    flags = {"--desc": False, "--stats": False}
    names = []
    i = 0
    while i < len(args):
        if args[i] in options and i + 1 < len(args):
            options[args[i]] = args[i + 1]
            i += 2
            continue
        if args[i] in flags:
            flags[args[i]] = True
        else:
            names.append(args[i])
        i += 1
    if len(names) != 1:
        console.print("[bold red]Usage:[/bold red] csvview <file.csv> [--sort col [--desc]] [--filter word] [--cols a,b] [--rows N] [--stats]")
        return False
    try:
        path = fs.resolve(names[0]) if fs else os.path.expanduser(names[0])
        if os.path.getsize(path) > LIMIT:
            console.print("[bold red]csvview: that file is bigger than 50 MB.[/bold red]")
            return False
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            header, rows = read_table(f.read())
    except OSError as e:
        console.print(f"[bold red]csvview: {names[0]}: {fs.errtext(e) if fs else e}[/bold red]")
        return False
    if not header:
        console.print("[yellow]The file is empty.[/yellow]")
        return False
    total = len(rows)
    if options["--filter"]:
        word = options["--filter"].lower()
        rows = [r for r in rows if any(word in c.lower() for c in r)]
    if options["--sort"]:
        index = column_index(header, options["--sort"])
        if index is None:
            console.print(f"[yellow]There is no column '{options['--sort']}'. The columns are: {', '.join(header)}[/yellow]")
            return False
        rows = sort_rows(rows, index, flags["--desc"])
    chosen = list(range(len(header)))
    if options["--cols"]:
        chosen = [column_index(header, c.strip()) for c in options["--cols"].split(",")]
        if None in chosen:
            console.print(f"[yellow]An unknown column in --cols. The columns are: {', '.join(header)}[/yellow]")
            return False
    if flags["--stats"]:
        table = Table(title="Number columns", header_style="bold blue")
        for column in ("Column", "Count", "Min", "Max", "Average", "Total"):
            table.add_column(column, justify="right" if column != "Column" else "left")
        for name, count, low, high, mean, whole in stats(header, rows):
            table.add_row(name, str(count), f"{low:g}", f"{high:g}", f"{mean:.4g}", f"{whole:.6g}")
        console.print(table if table.row_count else "[yellow]No column holds mostly numbers.[/yellow]")
        return True
    limit = max(1, int(options["--rows"])) if options["--rows"].isdigit() else 20
    table = Table(header_style="bold blue", row_styles=["", "dim"])
    for i in chosen:
        table.add_column(header[i], overflow="fold")
    for row in rows[:limit]:
        table.add_row(*[(row[i] if i < len(row) else "") for i in chosen])
    console.print(table)
    console.print(f"[dim]{min(limit, len(rows))} of {len(rows)} rows" + (f" (filtered from {total})" if len(rows) != total else "") + f", {len(header)} columns[/dim]")
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
