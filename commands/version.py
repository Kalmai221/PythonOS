import json
import os
import platform
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from pyos import export, lockdown

console = Console()
config = {
    "name": "version",
    "description": "Show the PythonOS version, which package it runs in (APK, Windows, Linux, ISO) and update status.",
    "alias": ["about"],
}


def core_version():
    try:
        return Path("VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        try:
            return str(json.loads(Path("config.json").read_text(encoding="utf-8")).get("version", "?"))
        except (OSError, ValueError):
            return "?"


def execute(args=None):
    info = export.info()
    table = Table(show_header=False, box=None)
    table.add_column(style="bold magenta", justify="right")
    table.add_column()
    table.add_row("PythonOS", core_version() + ("" if Path("VERSION").exists() else " (source checkout)"))
    if info:
        table.add_row("Package", f"{export.title(info['platform'])}, version {info['version']}")
        table.add_row("", "[dim]The package itself can't update from inside PythonOS; the core can ('updatecheck').[/dim]")
    else:
        table.add_row("Package", "none - running from source")
    table.add_row("Python", platform.python_version())
    table.add_row("System", f"{platform.system()} {platform.release()}")
    if lockdown.enabled():
        table.add_row("Mode", "locked down (nothing here can reach the system underneath)")

    try:
        state = json.loads((Path(".OSData") / "update_check.json").read_text(encoding="utf-8"))
        if state.get("core"):
            table.add_row("Update", f"PythonOS {state['core']} is available - run 'updatecheck'")
        if state.get("export"):
            table.add_row("Manual update", f"a newer package ({state['export'].split(':')[0]}) must be downloaded - run 'updatecheck'")
    except (OSError, ValueError):
        pass
    console.print(table)
    return True
