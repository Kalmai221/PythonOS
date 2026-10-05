from rich.console import Console

from core import sysupdate

console = Console()
config = {"name": "whatsnew", "description": "Show what the last update changed (release notes and changed files)."}


def execute(args=None):
    if not sysupdate.show_whats_new(force=True):
        console.print("[dim]No update has been installed on this system yet.[/dim]")
    return True
