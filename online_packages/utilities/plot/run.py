#!/usr/bin/env python3
"""Plot: charts in the terminal (plotext).

    plot 3 5 9 4 12                       a line through numbers
    plot data.csv                         the number columns of a CSV file, one line each
    plot data.csv --x month --y sales     choose the columns (--y a,b for several)
    plot data.csv --type bar              bar | line | scatter | hist
    plot data.csv --title "Sales"
"""
import csv
import io
import os
import sys

from rich.console import Console
from rich.text import Text

try:
    from pyos import fs
except ImportError:                                        # run on its own, outside PythonOS
    fs = None


def resolve(name):
    return fs.resolve(name) if fs else os.path.expanduser(name)

console = Console()
TYPES = ("line", "bar", "scatter", "hist")


def numeric(cell):
    cleaned = cell.replace("$", "").replace("%", "").replace(" ", "").strip()
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".") if cleaned.count(",") == 1 and len(cleaned.split(",")[1]) != 3 else cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def load_columns(text):
    """({column name: [cells]}, [column names in order]) from CSV text (the delimiter is detected)."""
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        return {}, []
    names = [h.strip() or f"col{i + 1}" for i, h in enumerate(rows[0])]
    columns = {n: [r[i].strip() if i < len(r) else "" for r in rows[1:]] for i, n in enumerate(names)}
    return columns, names


def number_columns(columns, names):
    """The names of the columns where most cells are numbers."""
    out = []
    for name in names:
        cells = [c for c in columns[name] if c]
        if cells and sum(numeric(c) is not None for c in cells) >= 0.8 * len(cells):
            out.append(name)
    return out


def draw(series, labels=None, kind="line", title="", width=None, height=None):
    """The chart text (with colour codes) for {name: [numbers]}. `labels` are the x positions or names."""
    import plotext as plt
    plt.clear_figure()
    plt.theme("clear")
    plt.plot_size(width or min(console.width, 100), height or 18)
    if title:
        plt.title(title)
    for name, values in series.items():
        xs = list(range(1, len(values) + 1))
        if kind == "bar":
            plt.bar(labels or [str(x) for x in xs], values, label=name if len(series) > 1 else None)
        elif kind == "scatter":
            plt.scatter(xs, values, label=name if len(series) > 1 else None)
        elif kind == "hist":
            plt.hist(values, bins=min(20, max(5, len(values) // 4)), label=name if len(series) > 1 else None)
        else:
            plt.plot(xs, values, label=name if len(series) > 1 else None)
    if labels and kind in ("line", "scatter") and len(labels) <= 24:
        plt.xticks(list(range(1, len(labels) + 1)), labels)
    return plt.build()


def execute(args=None):
    args = list(args or [])
    try:
        import plotext  # noqa: F401
    except ImportError:
        console.print("[bold red]plot needs the plotext library. Install the app again: pkg install plot[/bold red]")
        return False
    options = {"--x": None, "--y": None, "--type": "line", "--title": ""}
    rest = []
    i = 0
    while i < len(args):
        if args[i] in options and i + 1 < len(args):
            options[args[i]] = args[i + 1]
            i += 2
        else:
            rest.append(args[i])
            i += 1
    if options["--type"] not in TYPES:
        console.print(f"[yellow]Types: {', '.join(TYPES)}[/yellow]")
        return False
    if not rest:
        console.print("[bold red]Usage:[/bold red] plot <numbers...>   or   plot <file.csv> [--x col] [--y col,col] [--type line|bar|scatter|hist] [--title text]")
        return False
    labels = None
    if all(numeric(a) is not None for a in rest):
        series = {"values": [numeric(a) for a in rest]}
    else:
        try:
            with open(resolve(rest[0]), encoding="utf-8-sig", errors="replace", newline="") as f:
                columns, names = load_columns(f.read())
        except OSError as e:
            console.print(f"[bold red]plot: {rest[0]}: {fs.errtext(e) if fs else e}[/bold red]")
            return False
        if not names:
            console.print("[yellow]The file is empty.[/yellow]")
            return False
        wanted = [c.strip() for c in options["--y"].split(",")] if options["--y"] else [n for n in number_columns(columns, names) if n != options["--x"]]
        unknown = [c for c in wanted + ([options["--x"]] if options["--x"] else []) if c not in columns]
        if unknown:
            console.print(f"[yellow]No column {', '.join(unknown)}. The columns are: {', '.join(names)}[/yellow]")
            return False
        if not wanted:
            console.print("[yellow]No column holds numbers. Choose one with --y.[/yellow]")
            return False
        series = {n: [numeric(c) for c in columns[n]] for n in wanted}
        series = {n: [v for v in vals if v is not None] for n, vals in series.items()}
        if options["--x"]:
            labels = columns[options["--x"]][:len(next(iter(series.values())))]
    console.print(Text.from_ansi(draw(series, labels, options["--type"], options["--title"])))
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
