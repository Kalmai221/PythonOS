from rich.console import Console

import core_video
from core import hardware

console = Console()
config = {
    "name": "display",
    "description": "Screen resolution and text size: display [list | <width>x<height> | font]. For the live ISO and virtual machines.",
    "alias": ["resolution"],
    "exports": ["iso"],
}


def execute(args=None):
    args = args or []
    reason = hardware.unavailable_reason()
    if reason:
        console.print(f"[yellow]{reason}[/yellow]")
        return False
    if not args or args[0] in ("list", "ls", "status"):
        size = hardware.screen_size()
        console.print("Screen: " + (f"{size[0]} x {size[1]}" if size else "unknown"))
        modes = hardware.display_modes()
        console.print("Resolutions it offers: " + (", ".join(modes) if modes else "none reported") + "\nChange it with: display 1280x720   (text size: display font; display auto off stops the automatic choice in virtual machines)")
        note = core_video.unavailable_reason()
        if note:
            console.print(f"[dim]{note}[/dim]")
        return True
    if args[0] == "auto" and len(args) == 2 and args[1] in ("on", "off"):
        prefs = hardware.load_prefs().get("display", {})
        prefs["auto"] = args[1] == "on"
        hardware.save_pref("display", prefs)
        console.print(f"Automatic resolution is {args[1]}." + (" In a virtual machine with a small console, the next start picks a better resolution." if args[1] == "on" else ""))
        return True
    if args[0] in ("font", "size", "text"):
        return hardware.display_setup()
    return hardware.change_resolution(args[0])
