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
        console.print("Resolutions it offers: " + (", ".join(modes) if modes else "none reported") + "\nChange it with: display 1280x720   (text size: display font)")
        note = core_video.unavailable_reason()
        if note:
            console.print(f"[dim]{note}[/dim]")
        return True
    if args[0] in ("font", "size", "text"):
        return hardware.display_setup()
    return hardware.change_resolution(args[0])
