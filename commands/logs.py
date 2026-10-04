import os
from collections import deque
from rich.console import Console
from pyos.log import LOG_FILE

console = Console()
config = {"name": "logs", "description": "Show the system log (logs [N] shows the last N lines).", "alias": ["dmesg"]}


def execute(args=None):
    n = int(args[0]) if args and args[0].isdigit() else 20
    if not os.path.exists(LOG_FILE):
        console.print("[bold yellow]The system log is empty.[/bold yellow]")
        return
    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        lines = deque(f, maxlen=n)
    for line in lines:
        style = "red" if "[ERROR]" in line else "yellow" if "[WARN]" in line else None
        console.print(line.rstrip(), markup=False, highlight=False, style=style)
