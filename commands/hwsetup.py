from rich.console import Console
from core import hardware

console = Console()
config = {
    "name": "hwsetup",
    "description": "Hardware setup: hwsetup [check|audio|network|keyboard|timezone|bluetooth|display|printer]. Drivers, audio, Wi-Fi, keyboard, time zone, Bluetooth, display, printer.",
    "alias": ["hardware"],
    "exports": ["iso"],
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
    elif sub in ("keyboard", "keymap", "layout"):
        hardware.keyboard_setup()
    elif sub in ("timezone", "time", "tz", "clock"):
        hardware.timezone_setup()
    elif sub in ("bluetooth", "bt"):
        hardware.bluetooth_setup()
    elif sub in ("display", "screen", "resolution"):
        hardware.display_setup()
    elif sub in ("printer", "printers", "print"):
        hardware.printer_setup()
    elif sub == "":
        hardware.menu()
    else:
        console.print("[red]Usage:[/red] hwsetup \\[check|audio|network|keyboard|timezone|bluetooth|display|printer]")
        return False
