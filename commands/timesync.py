"""timesync: check the clock against the internet, and set it when it is wrong (the system must allow it)."""
import time

from rich.console import Console

console = Console()
config = {"name": "timesync", "description": "Check the clock against a time server and set it if it is wrong (timesync); a wrong clock breaks HTTPS and updates."}


def fmt(seconds):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(seconds))


def execute(args=None):
    from core import liveboot
    console.print("Asking a time server...")
    now = liveboot.network_time()
    if now is None:
        console.print("[bold red]No time server could be reached.[/bold red] Check the internet connection (ping example.com).")
        return False
    drift = now - time.time()
    console.print(f"Network time:   {fmt(now)}", highlight=False)
    console.print(f"This computer:  {fmt(time.time())}   ({'ahead' if drift < 0 else 'behind'} by {abs(int(drift))} seconds)", highlight=False)
    if abs(drift) <= liveboot.MAX_DRIFT:
        console.print("[green]The clock is right.[/green]")
        return True
    state, text = liveboot.sync_clock()
    if state == "set":
        console.print(f"[green]{text}.[/green]")
        return True
    console.print(f"[yellow]The clock was not changed: {text}.[/yellow] Set it in the system settings of this computer.")
    return state == "ok"
