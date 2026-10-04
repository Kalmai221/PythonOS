"""Persistent storage for the live ISO: a disk or partition labelled PYOS_DATA keeps accounts, files and settings.

* status()      - is persistent storage active, and where
* candidates()  - disks and partitions that could be used (nothing mounted, not the boot medium)
* create(dev)   - format one as PYOS_DATA, copy the current accounts/files/settings onto it
The boot side lives in OS_Export/ISO/overlay/pythonos-persist (it mounts the labelled partition before PythonOS starts).

Only fixed commands (lsblk, mkfs.ext4, mount, umount) are run, and only on a device that passed validate_device().
"""
import json
import os
import re
import shutil

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

from core import hardware
import pyos

console = Console()
LABEL = "PYOS_DATA"
MOUNT = "/mnt/pyos-data"
DEVICE_RE = re.compile(r"^/dev/(sd[a-z]{1,2}\d{0,2}|vd[a-z]{1,2}\d{0,2}|xvd[a-z]{1,2}\d{0,2}|nvme\d{1,2}n\d{1,2}(p\d{1,2})?|mmcblk\d{1,2}(p\d{1,2})?)$")


def active():
    return os.environ.get("PYOS_PERSISTENT") == "1"


def lsblk():
    """Block devices as a flat list of dicts: name, path, type, size, fstype, label, mountpoints, parent, removable."""
    code, out = hardware.run(["lsblk", "-J", "-b", "-o", "NAME,PATH,TYPE,SIZE,FSTYPE,LABEL,MOUNTPOINTS,RM,MODEL"])
    if code != 0:
        return []
    try:
        tree = json.loads(out)["blockdevices"]
    except (ValueError, KeyError):
        return []
    flat = []

    def walk(node, parent=None):
        item = {"name": node.get("name", ""), "path": node.get("path") or f"/dev/{node.get('name', '')}",
                "type": node.get("type", ""), "size": int(node.get("size") or 0), "fstype": node.get("fstype") or "",
                "label": node.get("label") or "", "mounts": [m for m in (node.get("mountpoints") or []) if m],
                "removable": str(node.get("rm")) in ("1", "True", "true"), "model": (node.get("model") or "").strip(),
                "parent": parent}
        flat.append(item)
        for child in node.get("children") or []:
            walk(child, item)

    for top in tree:
        walk(top)
    return flat


def _family_mounted(devices, dev):
    """True if this device, any partition of it or its parent is mounted or holds the boot medium."""
    related = [d for d in devices if d["path"] == dev["path"] or (d["parent"] and d["parent"]["path"] == dev["path"])]
    if dev["parent"]:
        related.append(dev["parent"])
    return any(d["mounts"] for d in related) or any(d["fstype"] in ("iso9660", "squashfs") for d in related)


def candidates(devices=None):
    """Devices PythonOS could turn into its data storage: real disks or partitions, nothing in use."""
    devices = devices if devices is not None else lsblk()
    found = []
    for d in devices:
        if d["type"] not in ("disk", "part") or not DEVICE_RE.match(d["path"]) or d["size"] < 64 * 1024 ** 2:
            continue
        if _family_mounted(devices, d):
            continue
        if d["type"] == "disk" and any(c["parent"] and c["parent"]["path"] == d["path"] for c in devices):
            continue              # a disk that already has partitions: pick one of them instead
        found.append(d)
    return found


def validate_device(path, devices=None):
    """(device dict or None, reason). Only a device from candidates() may be formatted."""
    if not DEVICE_RE.match(path or ""):
        return None, "That is not a disk or partition name (for example /dev/sdb or /dev/sdb1)."
    for d in candidates(devices):
        if d["path"] == path:
            return d, ""
    return None, f"{path} is in use, is the disk PythonOS started from, or already has partitions (choose one of them)."


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def existing():
    """A device already labelled PYOS_DATA, or None."""
    for d in lsblk():
        if d["label"] == LABEL:
            return d
    return None


def status():
    console.print("[bold]Persistent storage[/bold]")
    if active():
        console.print(f"[green]Active.[/green] Accounts, files and settings are saved on the {LABEL} disk "
                      f"(mounted at {MOUNT}).")
        return
    found = existing()
    if found:
        console.print(f"[yellow]A {LABEL} disk exists ({found['path']}, {human(found['size'])}) but was not in use at boot.[/yellow] "
                      "Shut down and start again with it plugged in.")
    else:
        console.print("[yellow]Not set up.[/yellow] Everything is forgotten when the computer shuts down. "
                      "Run [bold]persist create[/bold] to keep your accounts, files and settings on a disk or USB stick.")


def list_candidates():
    devices = lsblk()
    options = candidates(devices)
    if not options:
        console.print("[yellow]No suitable disk found.[/yellow] Plug in a USB stick or disk that is not in use "
                      "(the disk PythonOS started from cannot be used).")
        return options
    table = Table(title="Disks that can hold your data", header_style="bold blue")
    for col in ("#", "Device", "Size", "Type", "Currently holds"):
        table.add_column(col)
    for i, d in enumerate(options, 1):
        holds = d["label"] or d["fstype"] or "nothing recognisable"
        table.add_row(str(i), d["path"], human(d["size"]), ("USB/removable " if d["removable"] else "") + d["type"] + (f" {escape(d['model'])}" if d["model"] else ""), escape(holds))
    console.print(table)
    return options


def _copy_current(dest):
    """Seed the new storage with what the running system has (accounts, files, settings)."""
    for name in ("files", ".OSData"):
        if os.path.isdir(name):
            shutil.copytree(os.path.realpath(name), os.path.join(dest, name), dirs_exist_ok=True, symlinks=False)
    if os.path.isfile(pyos.paths.USER_DB):
        shutil.copy2(pyos.paths.USER_DB, os.path.join(dest, "users.json"))


def create(path=None):
    """Interactive: choose a device, confirm, format, copy the current data over."""
    reason = hardware.unavailable_reason()
    if reason:
        console.print(f"[yellow]{reason}[/yellow]")
        return False
    if active():
        console.print("[green]Persistent storage is already active.[/green]")
        return True
    if not path:
        options = list_candidates()
        if not options:
            return False
        pick = Prompt.ask("Number of the disk to use (blank to cancel)", default="").strip()
        if not pick.isdigit() or not 1 <= int(pick) <= len(options):
            console.print("[yellow]Cancelled.[/yellow]")
            return False
        path = options[int(pick) - 1]["path"]
    device, why = validate_device(path)
    if not device:
        console.print(f"[bold red]{escape(why)}[/bold red]")
        return False
    console.print(f"[bold red]This erases everything on {device['path']} ({human(device['size'])}"
                  + (f", currently holding {escape(device['label'] or device['fstype'])}" if device['label'] or device['fstype'] else "") + ").[/bold red]")
    if Prompt.ask(f"Type the device name ({device['path']}) to confirm, or anything else to cancel", default="").strip() != device["path"]:
        console.print("[yellow]Cancelled. Nothing was changed.[/yellow]")
        return False
    code, out = hardware.run(["mkfs.ext4", "-F", "-q", "-L", LABEL, device["path"]], timeout=300)
    if code != 0:
        console.print(f"[bold red]Could not format the disk (code {code}). {escape(out.strip()[-200:])}[/bold red]")
        return False
    os.makedirs(MOUNT, exist_ok=True)
    code, out = hardware.run(["mount", "-o", "nosuid,nodev,noexec", device["path"], MOUNT])
    if code != 0:
        console.print(f"[bold red]Formatted, but could not mount it: {escape(out.strip()[-200:])}[/bold red]")
        return False
    try:
        _copy_current(MOUNT)
        os.sync()
    finally:
        hardware.run(["umount", MOUNT])
    console.print(f"[bold green]Done.[/bold green] Your accounts, files and settings were copied to {device['path']}.\n"
                  "Keep it plugged in, then run [bold]shutdown[/bold] and start the computer again: from now on "
                  "everything is saved there automatically.")
    return True
