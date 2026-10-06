import os
import time
import datetime
from rich.console import Console

console = Console()
config = {"name": "uptime", "description": "Show how long PyOS has been running."}

BOOT_FILE = os.path.join(".OSData", "boot_time")


def execute(args=None):
    try:
        with open(BOOT_FILE) as f:
            booted = float(f.read().strip())
    except (OSError, ValueError):
        console.print("[bold red]uptime: boot time unknown[/bold red]")
        return
    secs = int(time.time() - booted)
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    up = (f"{d}d " if d else "") + f"{h:02d}:{m:02d}:{s:02d}"
    now = datetime.datetime.now().strftime("%H:%M:%S")
    try:
        from pyos import optional
        humanize = optional.get("humanize")
        words = f"  ({humanize.precisedelta(datetime.timedelta(seconds=secs), minimum_unit='seconds', format='%0.0f')})" if humanize and secs else ""
    except Exception:                                      # noqa: BLE001
        words = ""
    console.print(f"{now} up {up}{words}", markup=False)
