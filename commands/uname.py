import platform
from rich.console import Console
import pyos.fs as fs
from pyos import archinfo

console = Console()
config = {"name": "uname", "description": "Print system information (uname [-a])."}


def execute(args=None):
    parts = ["PyOS", fs.hostname(), platform.release() or "?", f"Python {platform.python_version()}", archinfo.arch() or platform.machine() or "?"]
    console.print(" ".join(parts) if args and "-a" in args else "PyOS", markup=False)
