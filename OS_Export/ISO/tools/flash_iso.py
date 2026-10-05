#!/usr/bin/env python3
"""Write a PythonOS ISO to a USB stick, safely.  Works on Windows, Linux and macOS (Python 3.8+, nothing to install).

    python flash_iso.py pythonos-1.2.0-x86_64.iso            choose the stick from a list
    python flash_iso.py pythonos-1.2.0-x86_64.iso --list     only show which drives could be used
    python flash_iso.py ISO --device /dev/sdb                name the drive yourself (Windows: 2, meaning PhysicalDrive2)

What it does, in this order, and stops at the first problem:
  1. checks the ISO against SHA256SUMS (next to it) or --sha256 <hash>
  2. lists only removable / USB drives that are not the one the computer runs from
  3. shows what will be erased and makes you type the drive name
  4. unmounts it (Windows: cleans the partition table), writes the image in 4 MB steps with a progress bar
  5. reads the stick back and compares it with the ISO

Needs administrator rights (Windows: an Administrator terminal; Linux/macOS: sudo). It never touches a drive you did not confirm.
If you prefer a graphical tool, balenaEtcher and Rufus (DD image mode) do the same job.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys

CHUNK = 4 * 1024 * 1024
SECTOR = 512
MIN_STICK = 1024 ** 3


# ----------------------------------------------------------------------------------------- checksums
def sha256_file(path, progress=None):
    digest = hashlib.sha256()
    total = os.path.getsize(path)
    done = 0
    with open(path, "rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            digest.update(block)
            done += len(block)
            if progress:
                progress(done, total)
    return digest.hexdigest()


def expected_hash(iso, given=None):
    """The hash the ISO should have: --sha256, or the line for it in SHA256SUMS next to it. None if neither exists."""
    if given:
        return given.strip().lower()
    sums = os.path.join(os.path.dirname(os.path.abspath(iso)), "SHA256SUMS")
    name = os.path.basename(iso)
    try:
        with open(sums, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(None, 1)
                if len(parts) == 2 and parts[1].lstrip("*") == name:
                    return parts[0].lower()
    except OSError:
        pass
    return None


# ----------------------------------------------------------------------------------------- finding drives
def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def parse_lsblk(text):
    """Drives from `lsblk -J -b -o NAME,PATH,SIZE,TYPE,RM,TRAN,MODEL,MOUNTPOINTS`: whole disks that are removable or on USB."""
    found = []
    for d in json.loads(text).get("blockdevices", []):
        if d.get("type") != "disk":
            continue
        removable = str(d.get("rm")) in ("1", "True", "true") or d.get("tran") == "usb"
        mounts = [m for c in d.get("children", []) or [] for m in (c.get("mountpoints") or []) if m]
        mounts += [m for m in (d.get("mountpoints") or []) if m]
        if removable and int(d.get("size") or 0) >= MIN_STICK and "/" not in mounts:
            found.append({"id": d.get("path") or "/dev/" + d["name"], "size": int(d["size"]), "name": (d.get("model") or "").strip() or "USB drive",
                          "mounts": mounts})
    return found


def parse_windows_disks(text):
    """Drives from PowerShell's Get-Disk as JSON: USB drives that are neither the system nor the boot disk."""
    data = json.loads(text) if text.strip() else []
    if isinstance(data, dict):
        data = [data]
    found = []
    for d in data:
        if str(d.get("BusType", "")).upper() != "USB" or d.get("IsSystem") or d.get("IsBoot") or int(d.get("Size") or 0) < MIN_STICK:
            continue
        found.append({"id": str(d["Number"]), "size": int(d["Size"]), "name": (d.get("FriendlyName") or "USB drive").strip(), "mounts": []})
    return found


def parse_diskutil(text):
    """Drives from `diskutil list -plist external physical` are read with plistlib by the caller; this takes the already parsed list."""
    return [{"id": f"/dev/{d['DeviceIdentifier']}", "size": int(d.get("Size", 0)), "name": d.get("Name", "USB drive"), "mounts": []}
            for d in text if int(d.get("Size", 0)) >= MIN_STICK]


def list_drives():
    system = platform.system()
    if system == "Linux":
        out = subprocess.run(["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,TYPE,RM,TRAN,MODEL,MOUNTPOINTS"], capture_output=True, text=True)
        return parse_lsblk(out.stdout)
    if system == "Windows":
        command = ("Get-Disk | Select-Object Number,FriendlyName,Size,BusType,IsSystem,IsBoot | ConvertTo-Json -Compress")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True)
        return parse_windows_disks(out.stdout)
    if system == "Darwin":
        import plistlib
        out = subprocess.run(["diskutil", "list", "-plist", "external", "physical"], capture_output=True)
        disks = []
        for entry in plistlib.loads(out.stdout).get("AllDisksAndPartitions", []):
            info = subprocess.run(["diskutil", "info", "-plist", entry["DeviceIdentifier"]], capture_output=True)
            detail = plistlib.loads(info.stdout)
            disks.append({"DeviceIdentifier": entry["DeviceIdentifier"], "Size": entry.get("Size", 0), "Name": detail.get("MediaName", "USB drive")})
        return parse_diskutil(disks)
    raise SystemExit(f"flash_iso: {system} is not supported")


def device_path(drive_id):
    """The raw device to open for writing."""
    if platform.system() == "Windows":
        return rf"\\.\PhysicalDrive{drive_id}"
    if platform.system() == "Darwin":
        return drive_id.replace("/dev/disk", "/dev/rdisk")      # the raw device is much faster
    return drive_id


# ----------------------------------------------------------------------------------------- preparing and writing
def prepare(drive):
    """Unmount (or, on Windows, clean) the drive so nothing else uses it while it is written."""
    system = platform.system()
    if system == "Linux":
        for mount in drive["mounts"]:
            subprocess.run(["umount", mount], check=False)
    elif system == "Darwin":
        subprocess.run(["diskutil", "unmountDisk", drive["id"]], check=True)
    elif system == "Windows":
        script = f"select disk {drive['id']}\nclean\n"
        subprocess.run(["diskpart"], input=script, text=True, check=True, capture_output=True)


def pad(block):
    """Raw drives on Windows only accept whole sectors."""
    remainder = len(block) % SECTOR
    return block + b"\0" * (SECTOR - remainder) if remainder else block


def progress_bar(label, done, total):
    width = 30
    filled = int(width * done / total) if total else width
    sys.stdout.write(f"\r{label} [{'#' * filled}{'-' * (width - filled)}] {done * 100 // max(1, total):>3}%  {human(done)} / {human(total)}")
    sys.stdout.flush()


def write_image(iso, target):
    total = os.path.getsize(iso)
    with open(iso, "rb") as src, open(target, "r+b", buffering=0) as dst:
        done = 0
        while True:
            block = src.read(CHUNK)
            if not block:
                break
            dst.write(pad(block))
            done += len(block)
            progress_bar("Writing  ", done, total)
        try:
            os.fsync(dst.fileno())
        except OSError:
            pass
    print()


def verify_image(iso, target):
    total = os.path.getsize(iso)
    want = hashlib.sha256()
    got = hashlib.sha256()
    with open(iso, "rb") as src, open(target, "rb", buffering=0) as dst:
        done = 0
        while done < total:
            size = min(CHUNK, total - done)
            a = src.read(size)
            b = b""
            while len(b) < len(a):
                part = dst.read(len(pad(a)) - len(b)) if platform.system() == "Windows" else dst.read(len(a) - len(b))
                if not part:
                    break
                b += part
            want.update(a)
            got.update(b[:len(a)])
            done += len(a)
            progress_bar("Verifying", done, total)
    print()
    return want.hexdigest() == got.hexdigest()


def is_admin():
    if platform.system() == "Windows":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


# ----------------------------------------------------------------------------------------- main
def main(argv=None):
    parser = argparse.ArgumentParser(description="Write a PythonOS ISO to a USB stick, safely.")
    parser.add_argument("iso", nargs="?", help="the .iso file")
    parser.add_argument("--list", action="store_true", help="only list the drives that could be used")
    parser.add_argument("--device", help="the drive to write to (Linux /dev/sdX, macOS /dev/diskN, Windows the disk number)")
    parser.add_argument("--sha256", help="the expected SHA-256 of the ISO (otherwise SHA256SUMS next to it is used)")
    parser.add_argument("--yes", action="store_true", help="do not ask for the drive name (only with --device, for scripts)")
    parser.add_argument("--no-verify", action="store_true", help="skip reading the stick back")
    args = parser.parse_args(argv)

    drives = list_drives()
    if args.list or not args.iso:
        if not drives:
            print("No USB stick found. Plug one in (at least 1 GB); the drive the computer runs from is never listed.")
        for d in drives:
            print(f"  {d['id']:<18} {human(d['size']):>9}  {d['name']}")
        return 0 if args.list else 2

    if not os.path.isfile(args.iso):
        print(f"flash_iso: {args.iso}: no such file")
        return 2
    if not is_admin():
        print("flash_iso: needs administrator rights (Windows: an Administrator terminal; Linux/macOS: run with sudo).")
        return 2

    want = expected_hash(args.iso, args.sha256)
    if want is None:
        print("Warning: no SHA256SUMS next to the ISO and no --sha256 given, so the download cannot be checked.")
        if input("Continue anyway? (yes/no) ").strip().lower() != "yes":
            return 2
    else:
        print("Checking the ISO...")
        have = sha256_file(args.iso, lambda d, t: progress_bar("Checking ", d, t))
        print()
        if have != want:
            print("flash_iso: the ISO does not match its checksum. The download is damaged or has been changed. Nothing was written.")
            return 1
        print("The ISO matches its checksum.")

    if not drives:
        print("No USB stick found. Plug one in (at least 1 GB).")
        return 2
    if args.device:
        drive = next((d for d in drives if d["id"] == args.device), None)
        if drive is None:
            print(f"flash_iso: {args.device} is not one of the usable drives (see --list). Internal and system drives are never offered.")
            return 2
    else:
        for number, d in enumerate(drives, 1):
            print(f"  {number}  {d['id']:<18} {human(d['size']):>9}  {d['name']}")
        pick = input("Number of the stick to erase (blank to cancel): ").strip()
        if not pick.isdigit() or not 1 <= int(pick) <= len(drives):
            print("Cancelled. Nothing was changed.")
            return 2
        drive = drives[int(pick) - 1]

    if os.path.getsize(args.iso) > drive["size"]:
        print("flash_iso: the stick is smaller than the ISO.")
        return 2
    print(f"\nEverything on {drive['id']} ({human(drive['size'])}, {drive['name']}) will be erased.")
    if not (args.yes and args.device):
        if input(f"Type {drive['id']} to continue: ").strip() != drive["id"]:
            print("Cancelled. Nothing was changed.")
            return 2

    prepare(drive)
    target = device_path(drive["id"])
    write_image(args.iso, target)
    if not args.no_verify:
        if not verify_image(args.iso, target):
            print("flash_iso: the stick does not match the ISO after writing. Try again or use another stick.")
            return 1
        print("Verified: the stick matches the ISO.")
    print("Done. Safely remove the stick, then start the computer from it (boot menu key, often F12 or Esc).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
