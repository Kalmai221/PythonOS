#!/usr/bin/env python3
import importlib.metadata
import os
import shutil
import socket
import subprocess
import sys
import sysconfig

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()
DIST = "ipython"
COMMAND = "ipython"
TITLE = "IPython"

# Different systems need different pip flags (venvs, Debian/Termux "externally managed"
# Python, read-only system site-packages), so try the safe options in order.
PIP_FLAG_SETS = [[], ["--user"], ["--break-system-packages"], ["--user", "--break-system-packages"]]


def is_installed():
    try:
        importlib.metadata.version(DIST)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def has_internet(host="pypi.org", port=443, timeout=3):
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except OSError:
        return False


def pip(action, *extra):
    """Run `pip <action> DIST`, retrying with other flag sets. Returns (ok, error_text)."""
    error = ""
    for flags in PIP_FLAG_SETS:
        result = subprocess.run([sys.executable, "-m", "pip", action, DIST, *extra, *flags],
                                capture_output=True, text=True)
        if result.returncode == 0:
            return True, ""
        error = (result.stderr or result.stdout or "").strip()
    return False, error


def main():
    if not is_installed():
        console.print(f"[bold yellow]{DIST} is not installed. Nothing to do.[/bold yellow]")
        return
    if not Confirm.ask(f"Remove {DIST} from this system?", default=False):
        console.print("[bold yellow]Uninstall cancelled.[/bold yellow]")
        return
    with console.status(f"[bold red]Removing {DIST}...[/bold red]", spinner="dots"):
        ok, error = pip("uninstall", "-y")
    if ok:
        console.print(f"[bold green]{DIST} removed.[/bold green]")
    else:
        console.print(Panel(f"[bold red]Could not remove {DIST}.[/bold red]\n\n{error[-800:]}", border_style="red"))
        sys.exit(1)


if __name__ == "__main__":
    main()


def execute():
    main()
