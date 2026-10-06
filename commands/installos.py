from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from core import installer, persist

console = Console()
config = {"name": "installos", "description": "Install PythonOS on a disk of this computer (from the live USB; erases that disk).",
          "alias": ["install-system"], "exports": ["iso"]}


def execute(args=None):
    reason = installer.available()
    if reason:
        console.print(f"[yellow]{escape(reason)}[/yellow]")
        return False
    console.print(Panel("[bold]Install PythonOS on this computer[/bold]\n\n"
                        "This makes a disk boot straight into PythonOS and keep your accounts and files, like a normal installed "
                        "system. The live USB stays as it is. [bold red]The disk you choose is erased completely.[/bold red]\n"
                        "[dim]Experimental: tried in virtual machines, not on every kind of computer. Keep a backup of anything important.[/dim]",
                        border_style="red", expand=False))
    options = installer.disks()
    if not options:
        console.print("[yellow]No disk can be used.[/yellow] It must be a whole disk of at least 2 GB that is not in use, and not the "
                      "USB stick PythonOS started from.")
        for path, size, why in installer.skipped():
            console.print(f"  {escape(path)}  {persist.human(size)}  [dim]{escape(why)}[/dim]")
        console.print("In a virtual machine, add another virtual hard disk (8 GB is plenty) in its settings, start it again and run installos again. "
                      "(The .ova download comes with an empty one.)")
        return False
    table = Table(title="Disks", header_style="bold blue")
    for col in ("#", "Device", "Size", "Model", "Currently holds"):
        table.add_column(col)
    devices = persist.lsblk()
    for i, d in enumerate(options, 1):
        holds = ", ".join(sorted({c["label"] or c["fstype"] for c in devices if c["parent"] and c["parent"]["path"] == d["path"]
                                  and (c["label"] or c["fstype"])})) or "nothing recognisable"
        if d.get("is_data"):
            holds = "[bold red]your PythonOS data disk (saved files and accounts)[/bold red]"
        table.add_row(str(i), d["path"], persist.human(d["size"]), escape(d["model"] or ("USB/removable" if d["removable"] else "")), holds if d.get("is_data") else escape(holds))
    console.print(table)
    try:
        pick = Prompt.ask("Number of the disk to erase and use (blank to cancel)", default="").strip()
        if not pick.isdigit() or not 1 <= int(pick) <= len(options):
            console.print("[yellow]Cancelled. Nothing was changed.[/yellow]")
            return False
        device = options[int(pick) - 1]
        console.print(f"\nWhat will happen to [bold]{device['path']}[/bold] ({persist.human(device['size'])}):")
        for number, text in enumerate(installer.plan(device), 1):
            console.print(f"  {number}. {escape(text)}")
        if device.get("is_data"):
            console.print("[bold red]This is the disk your saved files, accounts and settings are on. They are erased too.[/bold red] "
                          "Back up what you need first (backup).")
        typed = Prompt.ask(f"\nType the disk name [bold]{device['path']}[/bold] to erase it and install, or anything else to cancel", default="")
        if typed.strip() != device["path"]:
            console.print("[bold green]Cancelled. Nothing was changed.[/bold green]")
            return False
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled. Nothing was changed.[/yellow]")
        return False
    try:
        installer.install(device["path"], log=lambda text: console.print(f"[cyan]{escape(text)}[/cyan]"))
    except installer.InstallError as e:
        console.print(f"[bold red]The installation stopped: {escape(str(e))}[/bold red]")
        return False
    console.print("[bold green]PythonOS is installed.[/bold green] Shut down, remove the USB stick, and start the computer from the disk.")
    return True
