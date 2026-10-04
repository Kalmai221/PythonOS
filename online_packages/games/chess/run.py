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
DIST = "cli-chess"
COMMAND = "cli-chess"
TITLE = "CLI Chess"

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


def find_command():
    """Locate the command even when pip's scripts folder is not on PATH."""
    found = shutil.which(COMMAND)
    if found:
        return found
    dirs = [sysconfig.get_path("scripts")]
    try:
        dirs.append(sysconfig.get_path("scripts", f"{os.name}_user"))
    except Exception:
        pass
    for directory in dirs:
        for name in (COMMAND, COMMAND + ".exe"):
            candidate = os.path.join(directory or "", name)
            if directory and os.path.isfile(candidate):
                return candidate
    return None


def main():
    command = find_command()
    if not command:
        console.print(Panel(f"[bold red]{TITLE} is not installed.[/bold red]\n\n"
                            "Open the marketplace to install it, or run its installer from 'run programs'.",
                            border_style="red", expand=False))
        return
    extra = []
    if extra is None:
        return
    console.print(f"[bold green]Launching {TITLE}...[/bold green]\n")
    try:
        subprocess.run([command, *extra], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]{TITLE} exited with an error.[/bold red] {e}")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


def execute():
    main()
