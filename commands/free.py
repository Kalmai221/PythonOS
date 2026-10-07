from rich.console import Console
from rich.table import Table

from pyos import sysmem

console = Console()
config = {"name": "free", "description": "Show memory usage."}


def _h(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def execute(args=None):
    from pyos import resources
    total, used, available, percent = resources.snapshot()
    sw = sysmem.swap()                         # None where the system does not allow reading it (Android)
    table = Table(header_style="bold", box=None)
    for col in ("", "total", "used", "free", "use%"):
        table.add_column(col, justify="right" if col else "left")
    table.add_row("Mem:", _h(total), _h(used), _h(available), f"{percent:.0f}%")
    if not resources.limit_mb():
        if sw is not None:
            table.add_row("Swap:", _h(sw.total), _h(sw.used), _h(sw.free), f"{sw.percent:.0f}%")
        else:
            table.add_row("Swap:", "-", "-", "-", "not readable")
    console.print(table)
