from rich.console import Console
from rich.markup import escape
from rich.table import Table

import pyos
from pyos import tasks

console = Console()
config = {"name": "ps", "description": "List the tasks running in PythonOS (ps [-a] [-l]). See also: taskman, jobs, kill."}


def _human(n):
    return f"{n / 1024 ** 2:.1f}M" if n >= 1024 ** 2 else f"{n / 1024:.0f}K"


def execute(args=None):
    args = args or []
    everyone = any(a in ("-a", "-e", "-A", "-ef", "aux") for a in args)
    full = everyone or any(a in ("-l", "-f", "-ef", "aux") for a in args)
    user = pyos.userinfo()[0]
    rows = tasks.listing(user)
    if not everyone:
        rows = [r for r in rows if r["user"] == user]
    columns = ((("PID", "right"), ("PPID", "right"), ("USER", "left"), ("STAT", "left"), ("CPU%", "right"), ("MEM", "right"),
                ("TIME", "right"), ("COMMAND", "left")) if full else (("PID", "right"), ("TIME", "right"), ("COMMAND", "left")))
    table = Table(header_style="bold", box=None, pad_edge=False)
    for name, align in columns:
        table.add_column(name, justify=align)
    for r in rows:
        seconds = int(r["cpu_time"])
        clock = f"{seconds // 60:02d}:{seconds % 60:02d}"
        if full:
            table.add_row(str(r["pid"]), str(r["ppid"]), escape(r["user"]), r["state"][0].upper(), f"{r['cpu_percent']:.1f}",
                          _human(r["rss"]), clock, escape(r["cmd"]))
        else:
            table.add_row(str(r["pid"]), clock, escape(r["cmd"]))
    console.print(table)
    return True
