import os
import subprocess
import time
from rich.console import Console
from rich.progress import track
import sys
from yaspin import yaspin
import pyos

console = Console()

config = {
    "name": "restart",
    "description": "Restarts the OS",
    "alias": ["reboot"]
}

def restart_system():
    """Run the shutdown screen (without powering off), then start PythonOS again."""
    import core
    core.simulate_shutdown(restart=True)
    sys.exit(subprocess.call([sys.executable, "main.py"]))


def execute():
    """Prompt user to restart the system."""
    action = console.input("[bold yellow]Do you want to restart the system? (yes/no): [/bold yellow]").strip().lower()

    if action == "yes":
        restart_system()
    else:
        console.print("[bold yellow]System not responding...[/bold yellow]")

