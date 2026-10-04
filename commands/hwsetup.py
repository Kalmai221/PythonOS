from rich.console import Console
from core import hardware

console = Console()
config = {
    "name": "hwsetup",
    "description": "Hardware setup: hwsetup [check|audio|network]. Checks drivers/firmware, sets audio, connects to Wi-Fi.",
    "alias": ["hardware"],
}


def execute(args=None):
    reason = hardware.unavailable_reason()
    if reason:
        console.print(f"[yellow]{reason}[/yellow]")
        return False
    sub = (args[0].lower() if args else "")
    if sub in ("check", "hardware", "firmware"):
        hardware.hardware_check()
    elif sub in ("audio", "sound"):
        hardware.audio_setup()
    elif sub in ("network", "net", "wifi", "internet"):
        hardware.network_setup()
    elif sub == "":
        hardware.menu()
    else:
        console.print("[red]Usage:[/red] hwsetup [check|audio|network]")
        return False
