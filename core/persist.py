"""Persistent storage for the live ISO: a disk or partition labelled PYOS_DATA keeps accounts, files and settings.

* status()      - is persistent storage active, and where
* candidates()  - disks and partitions that could be used (nothing mounted, not the boot medium)
* create(dev)   - format one as PYOS_DATA (optionally encrypted), copy the current accounts/files/settings onto it
* health()      - free space, filesystem state, mount count and last mount time of the data disk
* resize()      - grow the filesystem to fill a disk or partition that was made bigger
* migrate(dev)  - move the data to another disk
The boot side lives in OS_Export/ISO/overlay/pythonos-persist (it mounts the labelled partition before PythonOS starts).

Only fixed commands (lsblk, mkfs.ext4, mount, umount) are run, and only on a device that passed validate_device().
"""
import json
import os
import re
import shutil
import time

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from core import hardware
import pyos

console = Console()
LABEL = "PYOS_DATA"
CRYPT_LABEL = "PYOS_CRYPT"          # a LUKS container; its inside is an ext4 labelled PYOS_DATA once opened
MAPPER = "pyosdata"
MOUNT = "/mnt/pyos-data"
STATE_FILE = os.path.join(".OSData", "persist.json")
DEVICE_RE = re.compile(r"^/dev/(sd[a-z]{1,2}\d{0,2}|vd[a-z]{1,2}\d{0,2}|xvd[a-z]{1,2}\d{0,2}|nvme\d{1,2}n\d{1,2}(p\d{1,2})?|mmcblk\d{1,2}(p\d{1,2})?)$")


def active():
    return os.environ.get("PYOS_PERSISTENT") == "1"


def encrypted():
    return os.environ.get("PYOS_PERSIST_ENCRYPTED") == "1"


def record_boot():
    """Called at start-up when the data disk is in use: remember when it was last used (shown by `persist status`)."""
    if not active():
        return
    try:
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, ValueError):
            state = {}
        state["previous_boot"] = state.get("last_boot")
        state["last_boot"] = time.time()
        state["boots"] = int(state.get("boots", 0)) + 1
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass


def mounted_device():
    """The device the data disk is mounted from, or None."""
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == MOUNT:
                    return parts[0]
    except OSError:
        pass
    return None


def parse_tune2fs(text):
    """The interesting lines of `tune2fs -l` as a dict."""
    wanted = {"Filesystem state": "state", "Last mount time": "last_mount", "Mount count": "mounts", "Filesystem created": "created",
              "Last checked": "last_check", "Filesystem volume name": "label", "Errors behavior": "errors"}
    found = {}
    for line in text.splitlines():
        key, _, value = line.partition(":")
        if key.strip() in wanted:
            found[wanted[key.strip()]] = value.strip()
    return found


def health():
    """Print how the data disk is doing."""
    if not active():
        console.print("[yellow]Persistent storage is not active, so there is nothing to check.[/yellow]")
        return False
    usage = shutil.disk_usage(MOUNT)
    pct = 100 * usage.used / max(1, usage.total)
    bar_colour = "green" if pct < 75 else "yellow" if pct < 90 else "red"
    filled = int(20 * pct / 100)
    dev = mounted_device()
    table = Table(show_header=False, box=None)
    table.add_row("Disk", f"{dev or '?'}" + ("  [green]encrypted (LUKS)[/green]" if encrypted() else "  [dim]not encrypted[/dim]"))
    table.add_row("Space", f"[{bar_colour}]{'#' * filled}[/{bar_colour}][dim]{'-' * (20 - filled)}[/dim] {pct:.0f}% used - "
                           f"{human(usage.free)} free of {human(usage.total)}")
    try:
        st = os.statvfs(MOUNT)
        if st.f_files:
            table.add_row("Files", f"{100 * (st.f_files - st.f_ffree) / st.f_files:.1f}% of the file slots used")
    except (OSError, AttributeError):
        pass
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    if state.get("previous_boot"):
        table.add_row("Last used", time.strftime("%Y-%m-%d %H:%M", time.localtime(state["previous_boot"])))
    if state.get("boots"):
        table.add_row("Boots with it", str(state["boots"]))
    if dev:
        code, out = hardware.run(["tune2fs", "-l", dev])
        if code == 0:
            info = parse_tune2fs(out)
            if info.get("state"):
                ok = info["state"].lower().startswith("clean")
                table.add_row("Filesystem", f"[{'green' if ok else 'red'}]{info['state']}[/{'green' if ok else 'red'}]"
                              + (f"  ({info['mounts']} mounts)" if info.get("mounts") else ""))
            if info.get("created"):
                table.add_row("Created", info["created"])
    console.print(Panel(table, title="[bold]Persistent storage[/bold]", border_style="blue", expand=False))
    if pct >= 90:
        console.print("[bold yellow]The data disk is almost full. Delete files, or grow it and run: persist resize[/bold yellow]")
    return True


def resize():
    """Grow the filesystem to the size of its disk or partition (after the disk was enlarged elsewhere)."""
    if not active():
        console.print("[yellow]Persistent storage is not active.[/yellow]")
        return False
    dev = mounted_device()
    if not dev:
        console.print("[red]Could not find which disk holds the data.[/red]")
        return False
    before = shutil.disk_usage(MOUNT).total
    code, out = hardware.run(["resize2fs", dev], timeout=600)
    if code != 0:
        console.print(f"[bold red]Could not resize ({escape(out.strip()[-200:])}).[/bold red]")
        return False
    after = shutil.disk_usage(MOUNT).total
    if after > before:
        console.print(f"[bold green]Grown from {human(before)} to {human(after)}.[/bold green]")
    else:
        console.print("[green]Already fills the whole disk.[/green] [dim](To make it bigger, enlarge the disk or partition first; "
                      "shrinking is not supported.)[/dim]")
    return True


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
        if d["label"] in (LABEL, CRYPT_LABEL):
            return d
    return None


def best_candidate(options=None):
    """The disk most worth offering: a removable one (a USB stick) first, then the biggest. None if nothing is suitable."""
    options = candidates() if options is None else options
    if not options:
        return None
    return sorted(options, key=lambda d: (not d["removable"], -d["size"]))[0]


def describe(device):
    kind = "USB stick" if device["removable"] else "disk"
    model = f" ({device['model'].strip()})" if device.get("model") else ""
    return f"{kind}{model}, {human(device['size'])}, at {device['path']}"


def hint():
    """One line for the login screen when storage is not set up but a disk that could hold it is plugged in; None otherwise."""
    try:
        if os.environ.get("PYOS_LIVE") != "1" or active():
            return None
        found = existing()
        if found:
            return (f"A {LABEL} disk ({found['path']}) is plugged in but was not in use at start-up. "
                    "Shut down and start again with it plugged in to use it. (persist status)")
        device = best_candidate()
        if device:
            return f"A {describe(device)} can keep your accounts, files and settings: run persist create."
    except Exception:
        pass
    return None


def status():
    console.print("[bold]Persistent storage[/bold]")
    if active():
        console.print(f"[green]Active.[/green] Accounts, files and settings are saved on the {LABEL} disk "
                      f"(mounted at {MOUNT}).")
        health()
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


def _passphrase():
    """Ask for a new passphrase twice. Returns it, or None if cancelled."""
    for _ in range(3):
        first = Prompt.ask("Passphrase for the data disk (at least 8 characters; you need it at every start)", password=True)
        if len(first) < 8:
            console.print("[yellow]Too short.[/yellow]")
            continue
        if Prompt.ask("Type it again", password=True) == first:
            return first
        console.print("[yellow]They did not match.[/yellow]")
    return None


def _format_plain(device, label):
    return hardware.run(["mkfs.ext4", "-F", "-q", "-L", label, device], timeout=300)


def _format_encrypted(device, passphrase):
    """LUKS2 container on the device, ext4 labelled PYOS_DATA inside. Returns (ok, message); the container is left closed."""
    if not hardware.have("cryptsetup"):
        return False, "cryptsetup is not installed on this system."
    code, out = hardware.run(["cryptsetup", "luksFormat", "--type", "luks2", "--label", CRYPT_LABEL, "-q", "--key-file=-", device],
                             timeout=300, text_input=passphrase)
    if code != 0:
        return False, f"luksFormat failed ({out.strip()[-150:]})"
    code, out = hardware.run(["cryptsetup", "open", "--type", "luks2", "--key-file=-", device, MAPPER + "-new"], timeout=60,
                             text_input=passphrase)
    if code != 0:
        return False, f"could not open the new container ({out.strip()[-150:]})"
    code, out = _format_plain("/dev/mapper/" + MAPPER + "-new", LABEL)
    hardware.run(["cryptsetup", "close", MAPPER + "-new"])
    return (code == 0), ("" if code == 0 else f"mkfs failed ({out.strip()[-150:]})")


def create(path=None, encrypt=False):
    """Interactive: choose a device, confirm, format, copy the current data over. encrypt=True makes a LUKS container."""
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
    passphrase = None
    if encrypt:
        passphrase = _passphrase()
        if not passphrase:
            console.print("[yellow]Cancelled. Nothing was changed.[/yellow]")
            return False
        console.print("[dim]Encrypting... (this can take a little while)[/dim]")
        ok, message = _format_encrypted(device["path"], passphrase)
        if not ok:
            console.print(f"[bold red]Could not set up the encrypted disk: {escape(message)}[/bold red]")
            return False
        code, out = hardware.run(["cryptsetup", "open", "--type", "luks2", "--key-file=-", device["path"], MAPPER + "-new"], timeout=60,
                                 text_input=passphrase)
        if code != 0:
            console.print(f"[bold red]Could not open the encrypted disk ({escape(out.strip()[-150:])}).[/bold red]")
            return False
        target = "/dev/mapper/" + MAPPER + "-new"
    else:
        code, out = _format_plain(device["path"], LABEL)
        if code != 0:
            console.print(f"[bold red]Could not format the disk (code {code}). {escape(out.strip()[-200:])}[/bold red]")
            return False
        target = device["path"]
    os.makedirs(MOUNT, exist_ok=True)
    code, out = hardware.run(["mount", "-o", "nosuid,nodev,noexec", target, MOUNT])
    if code != 0:
        console.print(f"[bold red]Formatted, but could not mount it: {escape(out.strip()[-200:])}[/bold red]")
        if encrypt:
            hardware.run(["cryptsetup", "close", MAPPER + "-new"])
        return False
    try:
        _copy_current(MOUNT)
        os.sync()
    finally:
        hardware.run(["umount", MOUNT])
        if encrypt:
            hardware.run(["cryptsetup", "close", MAPPER + "-new"])
    console.print(f"[bold green]Done.[/bold green] Your accounts, files and settings were copied to {device['path']}"
                  + (" (encrypted: you will be asked for the passphrase when the computer starts)" if encrypt else "") + ".\n"
                  "Keep it plugged in, then run [bold]shutdown[/bold] and start the computer again: from now on "
                  "everything is saved there automatically.")
    return True


def migrate(path=None):
    """Move the data to another disk. The new disk is erased and filled from the running data disk; at the next start the
    new disk is the one that is used and the old one is relabelled PYOS_OLD (nothing on it is deleted)."""
    if not active() or encrypted():
        console.print("[yellow]Migration needs plain persistent storage to be active (not encrypted). "
                      "For an encrypted disk, create a new one with 'persist create --encrypt' and copy with backup/restore.[/yellow]")
        return False
    old = mounted_device()
    if not old:
        console.print("[red]Could not find which disk holds the data.[/red]")
        return False
    if not path:
        options = list_candidates()
        if not options:
            return False
        pick = Prompt.ask("Number of the disk to move to (blank to cancel)", default="").strip()
        if not pick.isdigit() or not 1 <= int(pick) <= len(options):
            console.print("[yellow]Cancelled.[/yellow]")
            return False
        path = options[int(pick) - 1]["path"]
    device, why = validate_device(path)
    if not device:
        console.print(f"[bold red]{escape(why)}[/bold red]")
        return False
    used = shutil.disk_usage(MOUNT).used
    if device["size"] < used * 1.1:
        console.print(f"[bold red]{device['path']} ({human(device['size'])}) is too small for the {human(used)} of data.[/bold red]")
        return False
    console.print(f"[bold red]This erases everything on {device['path']} and copies your {human(used)} of data there.[/bold red]")
    if Prompt.ask(f"Type the device name ({device['path']}) to confirm, or anything else to cancel", default="").strip() != device["path"]:
        console.print("[yellow]Cancelled. Nothing was changed.[/yellow]")
        return False
    code, out = _format_plain(device["path"], "PYOS_NEW")
    if code != 0:
        console.print(f"[bold red]Could not format the new disk ({escape(out.strip()[-200:])}).[/bold red]")
        return False
    temp = MOUNT + "-new"
    os.makedirs(temp, exist_ok=True)
    code, out = hardware.run(["mount", "-o", "nosuid,nodev,noexec", device["path"], temp])
    if code != 0:
        console.print(f"[bold red]Could not mount the new disk ({escape(out.strip()[-200:])}).[/bold red]")
        return False
    try:
        with console.status("Copying your data..."):
            shutil.copytree(MOUNT, temp, dirs_exist_ok=True, symlinks=False, ignore=shutil.ignore_patterns("lost+found"))
            os.sync()
    except OSError as e:
        console.print(f"[bold red]Copying failed ({escape(str(e))}). The old disk is unchanged.[/bold red]")
        hardware.run(["umount", temp])
        return False
    hardware.run(["umount", temp])
    code1, _ = hardware.run(["e2label", old, "PYOS_OLD"])
    code2, _ = hardware.run(["e2label", device["path"], LABEL])
    if code1 or code2:
        hardware.run(["e2label", device["path"], "PYOS_NEW"])
        console.print("[bold red]Copied, but the labels could not be switched; the old disk is still the one in use.[/bold red]")
        return False
    console.print(f"[bold green]Done.[/bold green] {device['path']} will be used from the next start; the old disk ({old}) was "
                  "relabelled PYOS_OLD and its files were left alone. Run [bold]shutdown[/bold] and start again.")
    return True
