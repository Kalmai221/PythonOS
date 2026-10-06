import os
import platform

import psutil
from rich.console import Console
from rich.table import Table

from pyos import archinfo

console = Console()
config = {"name": "lscpu", "description": "Show the processor: family, cores, speed, load."}


def execute(args=None):
    table = Table(show_header=False, box=None)
    table.add_column(style="bold")
    table.add_column()
    freq = psutil.cpu_freq()
    rows = [("Family", archinfo.arch()), ("Description", archinfo.describe()), ("Processor", platform.processor() or "-"),
            ("Cores (logical)", str(os.cpu_count() or 1)), ("Cores (physical)", str(psutil.cpu_count(logical=False) or "-")),
            ("Speed", f"{freq.current:.0f} MHz" if freq else "-"), ("Load now", f"{psutil.cpu_percent(interval=0.3):.0f}%")]
    for key, value in rows:
        table.add_row(key, str(value))
    console.print(table)
    return True
