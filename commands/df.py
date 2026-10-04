import os
import shutil
from rich.console import Console
import pyos.fs as fs

console = Console()
config = {"name": "df", "description": "Show disk space, and how much the PyOS filesystem uses."}


def _h(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def execute(args=None):
    used = 0
    for root, _, files in os.walk(fs.BASE_DIR):
        for f in files:
            try:
                used += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    disk = shutil.disk_usage(fs.BASE_DIR)
    console.print(f"Filesystem  /   used by PyOS: {_h(used)}", markup=False)
    console.print(f"Host disk   total {_h(disk.total)}, free {_h(disk.free)} ({disk.used * 100 // disk.total}% used)", markup=False)
